"""Activate only the exact, unchanged version in a successful deployment report."""
from datetime import datetime
import re
import time
import httpx
from Backend.AI.app.services.salesforce_api_client import SalesforceApiClient,load_org_tokens,http_pool
from Backend.AI.app.services.metadata_safety import validate_component_name

def same_id(a,b):
    return isinstance(a,str) and isinstance(b,str) and len(a) in {15,18} and len(b) in {15,18} and a[:15]==b[:15]

class FlowActivationService:
    def __init__(self,owner,org,version,http=None):
        self.api=SalesforceApiClient(owner,org,version,http)

    def deployed_version(self,bundle,name):
        validate_component_name('Flow',name)
        if bundle.get('state')!='deployed' or bundle.get('operation')!='deploy':raise ValueError('Deploy this Flow successfully before activating it.')
        if not any(i.get('metadataType')=='Flow' and i.get('fullName')==name for i in bundle.get('components',[])):raise ValueError('This Flow is not in the deployed package.')
        result=bundle.get('lastResult',{}).get('result',{})
        if result.get('done') is not True or result.get('success') is not True or result.get('checkOnly') is True:raise ValueError('A successful real deployment report is required.')
        matches=[r for r in result.get('details',{}).get('componentSuccesses',[]) if r.get('componentType')=='Flow' and r.get('fullName')==name and r.get('success') is True]
        if len(matches)!=1 or not re.fullmatch(r'301[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',str(matches[0].get('id',''))):
            raise ValueError('The deployment report does not identify one exact Flow version. Activate it in Salesforce Setup or inspect the report; the app will not guess the latest version.')
        return matches[0]['id'],result.get('completedDate')

    def inspect(self,bundle,name):
        version_id,completed=self.deployed_version(bundle,name)
        rows=self.api.query("SELECT Id, DefinitionId, VersionNumber, Status, LastModifiedDate FROM Flow WHERE Id = '"+version_id+"'",tooling=True)['records']
        if len(rows)!=1 or not same_id(rows[0].get('Id'),version_id):raise ValueError('The deployed Flow version is no longer accessible.')
        flow=rows[0];definition=flow.get('DefinitionId');number=flow.get('VersionNumber')
        if not isinstance(number,int) or isinstance(number,bool) or number<1 or not re.fullmatch(r'300[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',str(definition or '')):raise ValueError('Flow version identity is incomplete.')
        rows=self.api.query("SELECT Id, DeveloperName, NamespacePrefix, ActiveVersionId, LatestVersionId FROM FlowDefinition WHERE Id = '"+definition+"'",tooling=True)['records']
        if len(rows)!=1 or not same_id(rows[0].get('Id'),definition) or rows[0].get('DeveloperName')!=name or rows[0].get('NamespacePrefix'):
            raise ValueError('The Flow definition does not match this deployed component.')
        info=rows[0]
        active=same_id(info.get('ActiveVersionId'),version_id) and flow.get('Status')=='Active'
        return {'versionId':version_id,'definitionId':definition,'versionNumber':number,'active':active,
            'flow':flow,'definition':info,'completed':completed}

    def verify_ready(self,info):
        if not same_id(info['definition'].get('LatestVersionId'),info['versionId']):raise ValueError('A newer Flow version exists. Review it in Salesforce before activating this deployed version.')
        if info['definition'].get('ActiveVersionId') and not same_id(info['definition']['ActiveVersionId'],info['versionId']):raise ValueError('Another Flow version is active. Review it in Salesforce before changing activation.')
        if info['flow'].get('Status')!='Draft':raise ValueError('Only the deployed Draft Flow can be activated here.')
        try:
            modified=datetime.fromisoformat(info['flow']['LastModifiedDate'].replace('Z','+00:00'))
            completed=datetime.fromisoformat(info['completed'].replace('Z','+00:00'))
            if modified>completed:raise ValueError('The deployed Flow was edited after deployment. Review a new package before activation.')
        except (KeyError,AttributeError,TypeError):raise ValueError('Flow modification time cannot be verified.') from None

    def patch(self,info):
        saved=load_org_tokens(self.api.owner,self.api.org)
        for attempt in range(2):
            try:
                response=(self.api.http or http_pool()).patch(saved['instance_url']+self.api.base+'/tooling/sobjects/FlowDefinition/'+info['definitionId'],
                    json={'Metadata':{'activeVersionNumber':info['versionNumber']}},headers={'Authorization':'Bearer '+saved['access_token'],'Accept':'application/json'})
            except httpx.HTTPError:raise RuntimeError('Activation outcome is unconfirmed. Check activation status; no request was automatically resubmitted.') from None
            if response.status_code==401 and attempt==0:
                saved=self.api._refresh(saved['access_token']);continue
            if response.status_code==204:return
            if 400<=response.status_code<500:
                message='Salesforce rejected Flow activation. Check Flow activation errors and Manage Flows permissions in Setup.'
                try:
                    errors=response.json()
                    if isinstance(errors,list) and errors and isinstance(errors[0],dict):message+=' '+str(errors[0].get('message',''))[:1000]
                except ValueError:pass
                for key in ('access_token','refresh_token'):message=message.replace(saved[key],'[redacted]')
                raise ValueError(message)
            raise RuntimeError('Activation outcome is unconfirmed. Check status before retrying.')

    def activate(self,bundle,name,save):
        info=self.inspect(bundle,name)
        states=bundle.setdefault('flowActivations',{})
        state=states.get(name,{})
        def update(status,message=''):
            states[name]={'state':status,'versionId':info['versionId'],'versionNumber':info['versionNumber'],'message':message,'updatedAt':time.time()}
            save(bundle)
        if info['active']:
            update('active','The deployed Flow version is active.');return
        if state.get('state') in {'running','unknown'}:
            update('unknown','Activation is not confirmed. Inspect this Flow in Salesforce Setup before another attempt.');return
        self.verify_ready(info)
        update('running','Activating the deployed Flow version…')
        try:
            self.patch(info)
            verified=self.inspect(bundle,name)
            if not verified['active']:raise RuntimeError('Salesforce accepted activation, but the active version is not confirmed. Check activation status.')
            update('active','The deployed Flow version is active.')
        except ValueError as error:
            update('failed',str(error));return
        except Exception:
            update('unknown','Activation outcome is unconfirmed. Check activation status; the app will not automatically repeat the request.');return
