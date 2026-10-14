"""Read-only org checks before a CREATE Flow deployment."""
import json
import shutil
import subprocess
from Backend.AI.app.validators.flow_validator import validate_flow, validate_flow_fields, validate_record_operations, flow_objects


class FlowPreflightService:
    def __init__(self, target_org='AIOrg'):
        self.target_org=target_org

    def _cli(self, args):
        from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
        from Backend.AI.app.services.flow_generator import api_version
        from pathlib import Path
        metadata=owned_metadata_api(self.target_org,api_version(Path.cwd()))
        if metadata:
            api=metadata.api
            if args[:3]==['org','list','metadata']:return api.list_components(args[args.index('--metadata-type')+1])
            if args[:2]==['sobject','describe']:return api.describe_object(args[args.index('--sobject')+1])
            if args[:2]==['data','query']:return api.query(args[args.index('--query')+1])
            raise ValueError('Unsupported API Flow preflight read.')
        executable=shutil.which('sf')
        if not executable: raise RuntimeError("Salesforce CLI 'sf' was not found in PATH.")
        try:
            from Backend.AI.app.services.sf_process import sf_arguments
            result=subprocess.run(sf_arguments([executable,*args,'--target-org',self.target_org,'--json']),capture_output=True,text=True,encoding='utf-8',errors='replace',check=False,timeout=120)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f'Flow preflight command could not complete: {exc}') from exc
        try: data=json.loads(result.stdout)
        except (ValueError,TypeError) as exc: raise RuntimeError('Flow preflight returned invalid JSON.') from exc
        if result.returncode or not isinstance(data,dict) or data.get('status') != 0:
            raise RuntimeError('Flow preflight failed: '+str(data.get('message','CLI error') if isinstance(data,dict) else 'Invalid response'))
        return data.get('result')

    def validate(self, plan):
        flows=[i for i in plan.items if i.action=='CREATE' and i.metadataType=='Flow']
        if not flows: return {'checkedFlows':[]}
        configs=[validate_flow(i.fullName,i.label,i.config) for i in flows]
        records=self._cli(['org','list','metadata','--metadata-type','Flow'])
        if not isinstance(records,list): raise RuntimeError('Flow discovery returned an unexpected result.')
        names={r.get('fullName') for r in records}
        cache={}
        planned_objects={i.fullName for i in plan.items if i.metadataType=='CustomObject' and i.action=='CREATE'}
        org_timezone=None
        for item,config in zip(flows,configs):
            if item.fullName in names:
                raise ValueError(f'Flow already exists: {item.fullName}. Flow v1 only supports creating a new Flow; choose a new API name.')
            for object_name in sorted(flow_objects(config)):
                if object_name not in cache and object_name not in planned_objects:
                    result=self._cli(['sobject','describe','--sobject',object_name])
                    if not isinstance(result,dict) or not isinstance(result.get('fields'),list):
                        raise RuntimeError('Flow object describe returned an unexpected result.')
                    cache[object_name]=result
            from Backend.AI.app.services.planned_context import context_with_planned_components
            merged=context_with_planned_components(plan.model_dump(), {'objects':[dict(value,name=name) for name,value in cache.items()]})
            cache={o['name']:o for o in merged['objects']}
            from Backend.AI.app.validators.flow_validator import ExtendedFlowConfig, validate_extended_context
            if isinstance(config, ExtendedFlowConfig):
                if config.schedule and org_timezone is None:
                    info=self._cli(['data','query','--query','SELECT TimeZoneSidKey FROM Organization LIMIT 1'])
                    rows=info.get('records',[]) if isinstance(info,dict) else []
                    org_timezone=rows[0].get('TimeZoneSidKey') if rows else None
                validate_extended_context(config,cache,check_write=True,org_timezone=org_timezone)
                continue
            validate_flow_fields(config,cache[config.object]['fields'],check_write=True)
            validate_record_operations(config,cache,check_write=True)
        return {'checkedFlows':[i.fullName for i in flows], 'status':'Draft', 'targetOrg':self.target_org}

    def validate_generated(self, plan, validation_result, project_root):
        """Ask Salesforce to compile the exact approved files without deploying.

        Formula syntax, installed action signatures, subflow contracts and screen
        combinations must be checked by the target org, not guessed locally.
        """
        from Backend.AI.app.validators.flow_validator import ExtendedFlowConfig
        from Backend.AI.app.services.deployment_service import SalesforceDeploymentService
        flows=[i for i in plan.items if i.action=='CREATE' and i.metadataType=='Flow']
        if not any(isinstance(validate_flow(i.fullName,i.label,i.config),ExtendedFlowConfig) for i in flows):
            return {'required':False}
        command=SalesforceDeploymentService(target_org=self.target_org,project_root=project_root).build_deploy_command(plan,validation_result)
        command.insert(4,'--dry-run')
        executable=shutil.which('sf')
        if not executable:raise RuntimeError("Salesforce CLI 'sf' was not found in PATH.")
        command[0]=executable
        try:
            from Backend.AI.app.services.sf_process import sf_arguments
            result=subprocess.run(sf_arguments(command),cwd=str(project_root),capture_output=True,text=True,encoding='utf-8',errors='replace',check=False,timeout=1900)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise RuntimeError('Salesforce Flow validation did not complete; no deployment was started.') from exc
        try:data=json.loads(result.stdout)
        except (ValueError,TypeError) as exc:raise RuntimeError('Salesforce Flow validation returned invalid JSON; no deployment was started.') from exc
        details=data.get('result') if isinstance(data,dict) else None
        if result.returncode or not isinstance(data,dict) or data.get('status')!=0 or not isinstance(details,dict) or details.get('done') is not True or details.get('success') is not True:
            errors=[]
            if isinstance(details,dict):
                failures=(details.get('details') or {}).get('componentFailures',[])
                if isinstance(failures,dict):failures=[failures]
                errors=[str(x.get('problem','Metadata validation failed')) for x in failures if isinstance(x,dict)]
            message='; '.join(errors) or (str(data.get('message','Validation failed or incomplete')) if isinstance(data,dict) else 'Unexpected response')
            raise ValueError('Salesforce Flow validation failed before deployment: '+message)
        return {'required':True,'success':True,'validationId':details.get('id')}
