"""Flow v1 contract, XML, org preflight and real HTTP pipeline with mocked I/O."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from Backend.AI.app.validators.flow_validator import validate_flow, validate_flow_fields
from Backend.AI.app.validators.plan_validator import ImplementationPlan, validate_plan
from Backend.AI.app.validators.metadata_spec_validator import MetadataSpecification
from Backend.AI.app.services.flow_generator import generate_flow, validate_flow_artifact, Q
from Backend.AI.app.services.flow_preflight_service import FlowPreflightService
from Backend.AI.app.services.metadata_generator import SalesforceMetadataGenerator
from Backend.AI.app.services.metadata_validator import SalesforceMetadataValidator
from Backend.AI.app.services.metadata_service import MetadataService
from Backend.AI.app.services.deployment_service import SalesforceDeploymentService
from Backend.AI.app.services.profile_fls_service import validate_create_specification
from Backend.AI.app.prompts.prompt_builder import build_planning_prompt, build_metadata_prompt


def config():
    return {
        'flowType':'RecordTriggered','triggerType':'RecordBeforeSave',
        'recordTriggerType':'CreateAndUpdate','object':'Account','status':'Draft',
        'startElement':'Check_Description','elements':[
            {'kind':'Decision','name':'Check_Description','label':'Check Description',
             'rules':[{'name':'Is_Blank','label':'Blank','conditionLogic':'or','conditions':[
                 {'field':'$Record.Description','operator':'IsNull','value':{'type':'Boolean','value':True}},
                 {'field':'$Record.Description','operator':'EqualTo','value':{'type':'String','value':''}},
             ],'next':'Set_Description'}], 'defaultLabel':'Keep existing','defaultNext':None},
            {'kind':'Assignment','name':'Set_Description','label':'Set Description',
             'assignments':[{'field':'$Record.Description','value':{'type':'String','value':'Pending review'}}], 'next':None}
        ]}


def plan_data(status='APPROVED'):
    return {'id':'PLAN-FLOW-001','requirementId':'REQ-FLOW-001','summary':'Default blank Account descriptions',
        'assumptions':[],'status':status,'items':[{'id':'ITEM-001','action':'CREATE','metadataType':'Flow',
        'fullName':'Account_Set_Default_Description','label':'Account Set Default Description',
        'description':'Set a default description only when blank.', 'dependencies':[], 'config':config(),
        'approval':'APPROVED' if status=='APPROVED' else 'PENDING',
        'validation':{'status':'PENDING','errors':[],'warnings':[]}}]}


def fields():
    return [{'name':'Description','type':'textarea','createable':True,'updateable':True,'calculated':False,'autoNumber':False,'length':32000}]


def context(): return {'objects':[{'name':'Account','label':'Account','fields':fields()}]}


@pytest.fixture
def project(tmp_path):
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    return tmp_path


def test_valid_plan_and_flow_contract():
    assert validate_plan(plan_data()).valid
    assert validate_flow('Account_Default','Account default',config()).object=='Account'


@pytest.mark.parametrize('change',[
    lambda c:c.update(flowType='Screen'), lambda c:c.update(triggerType='RecordAfterSave'),
    lambda c:c.update(recordTriggerType='Delete'), lambda c:c.update(status='Active'),
    lambda c:c.update(variables=[{"name":"Bad","dataType":"Number","value":{"type":"String","value":"wrong"}}]), lambda c:c.update(startElement='Missing'),
    lambda c:c['elements'][0]['rules'][0].update(next='Missing'),
    lambda c:c['elements'][1].update(next='Check_Description'),
    lambda c:c['elements'].append(dict(c['elements'][1],name='Unreachable')),
    lambda c:c['elements'][1].update(name='Check_Description'),
    lambda c:c['elements'][1]['assignments'][0].update(field='$Record.Id'),
    lambda c:c['elements'][1]['assignments'][0].update(field='$Record.Owner.Name'),
    lambda c:c['elements'][1]['assignments'][0].update(value={'type':'Number','value':True}),
    lambda c:c['elements'][0]['rules'][0]['conditions'][0].update(value={'type':'String','value':'true'}),
    lambda c:c['elements'][0]['rules'][0]['conditions'][0].update(operator='IsChanged'),
])
def test_rejects_unsupported_or_invalid_graph(change):
    c=config();change(c)
    with pytest.raises(ValueError):validate_flow('Account_Default','Account default',c)


@pytest.mark.parametrize('name',['../Bad','Object.Flow','Flow-1','ns__Flow','Flow_','1Flow'])
def test_rejects_unsafe_full_names(name):
    with pytest.raises(ValueError): validate_flow(name,'Label',config())


def test_create_update_and_create_and_update():
    for event in ['Create','Update','CreateAndUpdate']:
        c=config();c['recordTriggerType']=event
        assert validate_flow('Example','Example',c).recordTriggerType==event


def test_xml_encodes_decision_assignment_and_draft(project):
    plan=ImplementationPlan.model_validate(plan_data())
    paths=SalesforceMetadataGenerator(project).generate(plan)
    assert len(paths) == 1
    assert Path(paths[0]) == project / 'force-app/main/default/flows/Account_Set_Default_Description.flow-meta.xml'
    root=ET.parse(paths[0]).getroot()
    assert root.findtext(Q('status'))=='Draft'
    assert root.findtext(Q('processType'))=='AutoLaunchedFlow'
    assert root.findtext(f'{Q("start")}/{Q("triggerType")}')=='RecordBeforeSave'
    assert root.findtext(f'{Q("start")}/{Q("recordTriggerType")}')=='CreateAndUpdate'
    assert root.findtext(f'{Q("assignments")}/{Q("assignmentItems")}/{Q("operator")}')=='Assign'
    assert root.findtext(f'{Q("assignments")}/{Q("assignmentItems")}/{Q("assignToReference")}')=='$Record.Description'
    assert root.find(f'{Q("decisions")}/{Q("defaultConnector")}') is None
    assert SalesforceMetadataValidator(project).validate(plan)['valid']


def test_xml_escapes_business_text(project):
    item=ImplementationPlan.model_validate(plan_data()).items[0]
    item.config['elements'][1]['assignments'][0]['value']['value']='A & B <review>'
    p=generate_flow(item,project)
    assert 'A &amp; B &lt;review&gt;' in p.read_text()
    validate_flow_artifact(p,item,project)


@pytest.mark.parametrize('tamper',['Active','Wrong value','Foreign XML'])
def test_tampered_xml_blocks_local_validation_and_deploy(project,tamper):
    plan=ImplementationPlan.model_validate(plan_data());item=plan.items[0]
    path=generate_flow(item,project)
    xml=path.read_text()
    if tamper=='Active':xml=xml.replace('<status>Draft</status>','<status>Active</status>')
    elif tamper=='Wrong value':xml=xml.replace('Pending review','Do something else')
    else:xml='<Other/>'
    path.write_text(xml)
    assert not SalesforceMetadataValidator(project).validate(plan)['valid']
    with pytest.raises(ValueError):
        SalesforceDeploymentService(project_root=project).build_deploy_command(plan,{'valid':True,'deploymentFiles':[str(path)]})


def test_flow_requires_explicit_files_and_missing_file_fails(project):
    plan=ImplementationPlan.model_validate(plan_data())
    assert not SalesforceMetadataValidator(project).validate(plan)['valid']
    with pytest.raises(ValueError,match='explicit'):
        SalesforceDeploymentService(project_root=project).build_deploy_command(plan,{'valid':True})


def test_flow_only_spec_copies_approved_config_without_ai():
    plan=ImplementationPlan.model_validate(plan_data());provider=Mock()
    spec=MetadataService(provider).generate_specification(plan)
    provider.generate.assert_not_called()
    assert spec.metadata[0].config==plan.items[0].config
    validate_create_specification(plan,spec)
    spec.metadata[0].config['elements'][1]['assignments'][0]['value']['value']='Changed'
    with pytest.raises(ValueError,match='changed the approved'):
        validate_create_specification(plan,spec)


def test_unapproved_flow_item_cannot_generate_spec():
    plan=ImplementationPlan.model_validate(plan_data());plan.items[0].approval='PENDING'
    with pytest.raises(ValueError,match='APPROVED'): MetadataService(Mock()).generate_specification(plan)


def test_unknown_or_readonly_fields_rejected():
    parsed=validate_flow('Example','Example',config())
    with pytest.raises(ValueError,match='unknown field'):validate_flow_fields(parsed,[])
    for bad in [dict(fields()[0],updateable=False),dict(fields()[0],calculated=True),dict(fields()[0],type='boolean')]:
        with pytest.raises(ValueError):validate_flow_fields(parsed,[bad],check_write=True)


def test_preflight_checks_existing_flow_and_field_access():
    plan=ImplementationPlan.model_validate(plan_data());service=FlowPreflightService()
    service._cli=Mock(side_effect=[[],{'fields':fields()}])
    assert service.validate(plan)['status']=='Draft'
    service._cli=Mock(return_value=[{'fullName':plan.items[0].fullName}])
    with pytest.raises(ValueError,match='already exists'):service.validate(plan)
    service._cli=Mock(side_effect=[[],{'fields':[dict(fields()[0],updateable=False)]}])
    with pytest.raises(ValueError,match='not writable'):service.validate(plan)


def test_prompt_contract_and_schema_cover_flow():
    planning=build_planning_prompt('Create Account flow',context())
    metadata=build_metadata_prompt(plan_data(),context())
    for prompt in [planning,metadata]:
        assert 'INTEGRATED FLOW CONTRACT' in prompt and '<FLOW_CONFIG_SCHEMA>' in prompt and 'RecordBeforeSave' in prompt and 'Draft' in prompt
    autolaunched = build_planning_prompt('Create an Autolaunched Flow', context())
    scheduled = build_planning_prompt('Create a Scheduled Flow', context())
    assert 'AUTOLAUNCHED RECORD-ID RESOURCE RULES' in autolaunched
    assert 'IsNull' in autolaunched and 'Never compare an Id to an empty String' in autolaunched
    assert 'AUTOLAUNCHED RECORD-ID RESOURCE RULES' not in scheduled
    assert 'Because Flow generation is not currently executable' not in planning
    schema=json.loads((Path(__file__).resolve().parents[4]/'Prompt Engineering/Schemas/flow-config-v001.json').read_text())
    assert all(schema['$defs'][branch['$ref'].split('/')[-1]]['properties']['status']['const']=='Draft' for branch in schema['anyOf'])


def test_real_http_generate_approve_metadata_deploy(project,monkeypatch):
    from Backend.AI.app import main
    monkeypatch.chdir(project)
    provider=Mock();provider.generate.return_value=json.dumps(plan_data('DRAFT'))
    monkeypatch.setattr(main,'get_ai_provider',lambda:provider)
    from Backend.AI.app.services.plan_store import PlanStore
    from Backend.AI.app.services.metadata_spec_store import MetadataSpecStore
    monkeypatch.setattr(main,'plan_store',PlanStore())
    monkeypatch.setattr(main,'metadata_spec_store',MetadataSpecStore())
    monkeypatch.setattr(FlowPreflightService,'_cli',lambda self,args: [] if args[0]=='org' else {'fields':fields()})
    monkeypatch.setattr(main.PageLayoutService,'_retrieve',Mock(side_effect=AssertionError('Flow-only should not retrieve layouts')))
    observed={}
    def deploy(executor,plan,validation_result):
        command=executor.deployment_service.build_deploy_command(plan,validation_result)
        observed['command']=command
        observed['files']=validation_result['deploymentFiles']
        assert command.count('--source-dir')==1
        assert observed['files'][0].endswith('.flow-meta.xml')
        return {'success':True}
    monkeypatch.setattr(main.SalesforceDeploymentExecutor,'deploy',deploy)
    with TestClient(main.app) as client:
        response=client.post('/api/plan',json={'requirement':'Create a before-save Account flow to default blank Description','salesforce_context':context()})
        assert response.status_code==200,response.text
        plan_id=response.json()['id']
        assert client.post(f'/api/plans/{plan_id}/approve').status_code==200
        response=client.post(f'/api/plans/{plan_id}/generate-metadata')
        assert response.status_code==200,response.text
        assert provider.generate.call_count==1
        response=client.post(f'/api/plans/{plan_id}/deploy')
        assert response.status_code==200,response.text
        assert response.json()['pageLayouts']['layouts']==[]
        assert response.json()['systemAdministratorFLS']['generatedFiles']==[]
        assert response.json()['flowPreflight']['status']=='Draft'
    assert observed['files']
