"""LWC router: local access or configured bearer token; server allowlisted orgs."""
import hmac
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from Backend.AI.app.providers.provider_factory import get_ai_provider
from Backend.AI.app.services.lwc_service import LWCAutomationService, LWCRequest
from Backend.AI.app.services.lwc_store import LWCStore

class DeploymentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approved: bool = False
    source_hash: str = ''

class LWCWorkflow:
    def __init__(self,project_root='.',provider_factory=get_ai_provider,service=None,allowed_orgs=None,api_token=None):
        self.service = service or LWCAutomationService(project_root)
        self.provider_factory = provider_factory
        self.allowed_orgs = set(allowed_orgs if allowed_orgs is not None else
                                [x.strip() for x in os.getenv('LWC_ALLOWED_ORGS','AIOrg').split(',') if x.strip()])
        self.api_token = api_token if api_token is not None else os.getenv('LWC_API_TOKEN','')
        self.store = LWCStore(Path(project_root)/'runtime/lwc/bundles.sqlite3')
        self.router = APIRouter(prefix='/api/lwc',tags=['LWC automation'],dependencies=[Depends(self.authorize)])
        for path,handler,method in [('/generate',self.generate,'POST'),('/bundles/{bundle_id}',self.get,'GET'),
                ('/bundles/{bundle_id}/download',self.download,'GET'),('/bundles/{bundle_id}/validate',self.validate,'POST'),
                ('/bundles/{bundle_id}/deploy',self.deploy,'POST'),('/bundles/{bundle_id}/report',self.report,'POST')]:
            self.router.add_api_route(path,handler,methods=[method])

    def authorize(self,request:Request):
        if self.api_token:
            supplied = request.headers.get('authorization','')
            if not hmac.compare_digest(supplied,'Bearer '+self.api_token):
                raise HTTPException(401,'LWC service requires its configured bearer token.')
        elif request.client is None or request.client.host not in {'127.0.0.1','::1','localhost','testclient'}:
            raise HTTPException(403,'Local use only. Set LWC_API_TOKEN before remote access; use a trusted HTTPS gateway.')

    def allowed(self,org):
        if org not in self.allowed_orgs:
            raise HTTPException(403,'Target org is not in the server LWC_ALLOWED_ORGS configuration.')

    def get(self,bundle_id:str):
        try:
            bundle = self.store.get(bundle_id)
        except KeyError as exc:
            raise HTTPException(404,'LWC bundle not found.') from exc
        self.allowed(bundle['targetOrg'])
        return bundle

    def generate(self,request:LWCRequest):
        self.allowed(request.target_org)
        try:
            bundle = self.service.generate(request,self.provider_factory())
            self.store.put(bundle)
            return bundle
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(503,'Start from your Salesforce AI folder; install the listed LWC tooling files.') from exc
        except Exception as exc:
            raise HTTPException(502,'LWC generation failed. Check configured provider, CLI authorization and tooling.') from exc

    def download(self,bundle_id:str):
        bundle = self.get(bundle_id)
        return Response(self.service.archive(bundle),media_type='application/zip',
                        headers={'Content-Disposition':f'attachment; filename="{bundle["componentName"]}.zip"'})

    def validate(self,bundle_id:str):
        return self.run(bundle_id,dry_run=True)

    def deploy(self,bundle_id:str,request:DeploymentRequest):
        bundle = self.get(bundle_id)
        if not request.approved or request.source_hash != bundle['sourceHash']:
            raise HTTPException(422,'Review the files, then submit approved=true and the exact sourceHash as source_hash.')
        return self.run(bundle_id,dry_run=False)

    def save_result(self,bundle_id,payload,operation):
        details = payload.get('result',{})
        if not isinstance(details,dict):
            raise RuntimeError('Unexpected deployment response; inspect org deployment status.')
        pending = details.get('done') is False or details.get('status') in {'Pending','Queued','InProgress','Canceling'}
        state = 'pending' if pending else ('validated' if operation=='validate' else 'deployed') if details.get('success') is True else 'failed'
        return self.store.finish(bundle_id,state=state,operation=operation,jobId=details.get('id'),lastResult=payload)

    def run(self,bundle_id,dry_run):
        self.get(bundle_id)
        try:
            bundle = self.store.claim(bundle_id,'validate' if dry_run else 'deploy')
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from exc
        operation = 'validate'
        try:
            # Refresh compilation in the same org immediately before deployment.
            payload = self.service.deploy(bundle,dry_run=True)
            details = payload.get('result', {})
            complete = (isinstance(details, dict) and details.get('success') is True
                        and details.get('done') is not False
                        and details.get('status') not in {'Pending','Queued','InProgress','Canceling'})
            if dry_run or not complete:
                return self.save_result(bundle_id,payload,'validate')
            self.store.finish(bundle_id,state='running',operation='deploy',dryRun=payload)
            operation = 'deploy'
            payload = self.service.deploy(bundle,dry_run=False)
            return self.save_result(bundle_id,payload,'deploy')
        except ValueError as exc:
            self.store.finish(bundle_id,state='failed',operation=operation,error=str(exc))
            raise HTTPException(422,str(exc)) from exc
        except Exception as exc:
            self.store.finish(bundle_id,state='unknown',operation=operation,error='CLI outcome requires inspection.')
            raise HTTPException(502,'Operation outcome unknown. Check saved job/report or Salesforce Deployment Status before retrying.') from exc

    def report(self,bundle_id:str):
        bundle = self.get(bundle_id)
        if bundle.get('state') not in {'pending','unknown'}:
            raise HTTPException(409,'Report is available for saved pending/unknown jobs.')
        try:
            return self.save_result(bundle_id,self.service.report(bundle),bundle.get('operation','validate'))
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502,'Unable to retrieve deployment status. Check Salesforce Deployment Status.') from exc
