"""Apex routes reuse the established approval/deployment state machine."""
import hmac
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from Backend.AI.app.api.lwc_api import LWCWorkflow
from Backend.AI.app.providers.provider_factory import get_ai_provider
from Backend.AI.app.services.apex_service import ApexAutomationService, ApexRequest
from Backend.AI.app.services.apex_store import ApexStore

class ApexWorkflow(LWCWorkflow):
    def __init__(self,project_root='.',provider_factory=get_ai_provider,service=None,allowed_orgs=None,api_token=None):
        self.service = service or ApexAutomationService(project_root)
        self.provider_factory = provider_factory
        self.allowed_orgs = set(allowed_orgs if allowed_orgs is not None else
            [item.strip() for item in os.getenv('APEX_ALLOWED_ORGS','AIOrg').split(',') if item.strip()])
        self.api_token = api_token if api_token is not None else os.getenv('APEX_API_TOKEN','')
        self.store = ApexStore(Path(project_root)/'runtime/apex/bundles.sqlite3')
        self.router = APIRouter(prefix='/api/apex',tags=['Apex automation'],dependencies=[Depends(self.authorize)])
        for path,handler,method in [('/generate',self.generate,'POST'),('/bundles/{bundle_id}',self.get,'GET'),
            ('/bundles/{bundle_id}/download',self.download,'GET'),('/bundles/{bundle_id}/validate',self.validate,'POST'),
            ('/bundles/{bundle_id}/deploy',self.deploy,'POST'),('/bundles/{bundle_id}/report',self.report,'POST')]:
            self.router.add_api_route(path,handler,methods=[method])

    def authorize(self,request:Request):
        if self.api_token:
            if not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+self.api_token):
                raise HTTPException(401,'Apex service requires its configured bearer token.')
        elif request.client is None or request.client.host not in {'127.0.0.1','::1','localhost','testclient'}:
            raise HTTPException(403,'Local use only. Configure APEX_API_TOKEN for remote access through HTTPS.')

    def allowed(self,org):
        if org not in self.allowed_orgs:
            raise HTTPException(403,'Target org is not in APEX_ALLOWED_ORGS.')

    def get(self,bundle_id:str):
        try:
            bundle = self.store.get(bundle_id)
        except KeyError as exc:
            raise HTTPException(404,'Apex package not found.') from exc
        self.allowed(bundle['targetOrg'])
        return bundle

    def generate(self,request:ApexRequest):
        self.allowed(request.target_org)
        try:
            bundle = self.service.generate(request,self.provider_factory())
            self.store.put(bundle)
            return bundle
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502,'Apex generation failed. Check provider, project configuration and org authorization.') from exc

    def save_result(self,bundle_id,payload,operation):
        self.service.require_test_execution(payload)
        return super().save_result(bundle_id,payload,operation)

    def run(self,bundle_id,dry_run):
        self.get(bundle_id)
        try:
            bundle = self.store.claim(bundle_id,'validate' if dry_run else 'deploy')
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from exc
        operation = 'validate'
        try:
            payload = self.service.deploy(bundle,dry_run=True)
            details = payload.get('result',{})
            complete = (isinstance(details,dict) and details.get('success') is True
                and details.get('done') is not False
                and details.get('status') not in {'Pending','Queued','InProgress','Canceling'})
            if dry_run or not complete:
                return self.save_result(bundle_id,payload,'validate')
            self.service.require_test_execution(payload)
            # A dry-run job ID must never be reported as the real deployment.
            self.store.finish(bundle_id,state='running',operation='deploy',dryRun=payload,jobId=None)
            operation = 'deploy'
            payload = self.service.deploy(bundle,dry_run=False)
            return self.save_result(bundle_id,payload,'deploy')
        except ValueError as exc:
            self.store.finish(bundle_id,state='failed',operation=operation,error=str(exc))
            raise HTTPException(422,str(exc)) from exc
        except Exception as exc:
            self.store.finish(bundle_id,state='unknown',operation=operation,error='CLI outcome requires inspection.')
            raise HTTPException(502,'Operation outcome unknown. Inspect Salesforce Deployment Status before retrying.') from exc
