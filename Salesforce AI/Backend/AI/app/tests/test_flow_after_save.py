from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock
import xml.etree.ElementTree as ET
import pytest
from fastapi.testclient import TestClient

from Backend.AI.app.tests.test_flow_pipeline import plan_data, config as before_config
from Backend.AI.app.validators.flow_validator import validate_flow, validate_flow_context, validate_record_operations
from Backend.AI.app.validators.plan_validator import ImplementationPlan
from Backend.AI.app.services.flow_generator import generate_flow, Q, validate_flow_artifact
from Backend.AI.app.services.flow_preflight_service import FlowPreflightService
from Backend.AI.app.services.metadata_service import MetadataService
from Backend.AI.app.services.metadata_validator import SalesforceMetadataValidator
from Backend.AI.app.services.deployment_service import SalesforceDeploymentService


def record_field(name, kind='string', **kwargs):
    return dict(name=name,type=kind,createable=True,updateable=True,filterable=True,
                nillable=True,defaultedOnCreate=False,**kwargs)


def objects():
    return {
        'Account':{'name':'Account','createable':True,'updateable':True,'fields':[
            dict(name='Id',type='id'),record_field('Description','textarea'),
            record_field('OwnerId','reference',referenceTo=['User'])]},
        'Task':{'name':'Task','createable':True,'updateable':True,'fields':[
            record_field('Subject'),record_field('WhatId','reference',referenceTo=['Account','Opportunity']),
            record_field('OwnerId','reference',referenceTo=['User','Group'])]},
        'Contact':{'name':'Contact','createable':True,'updateable':True,'fields':[
            record_field('AccountId','reference',referenceTo=['Account']),record_field('Description','textarea'),
            record_field('Title')]},
    }


def after_config(update=False):
    node={'kind':'CreateRecords','name':'Create_Task','label':'Create follow-up Task','object':'Task',
          'inputAssignments':[{'field':'Subject','value':{'type':'String','value':'Follow up'}},
                              {'field':'WhatId','value':{'type':'Reference','value':'$Record.Id'}}],
          'next':None}
    if update:
        node={'kind':'UpdateRecords','name':'Update_Contacts','label':'Update related Contacts','object':'Contact',
              'relationshipField':'AccountId','filters':[{'field':'Title','operator':'EqualTo','value':{'type':'String','value':'Manager'}}],
              'inputAssignments':[{'field':'Description','value':{'type':'String','value':'Review required'}}],'next':None}
    return {'flowType':'RecordTriggered','triggerType':'RecordAfterSave','recordTriggerType':'Create',
            'object':'Account','status':'Draft','startElement':node['name'],'elements':[node]}


def plan(update=False,status='APPROVED'):
    data=plan_data(status);data['items'][0]['config']=after_config(update)
    data['items'][0]['fullName']='Account_Create_Follow_Up' if not update else 'Account_Update_Contacts'
    data['items'][0]['label']='Account related records';data['items'][0]['description']='Related record automation'
    return ImplementationPlan.model_validate(data)


@pytest.fixture
def project(tmp_path):
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    return tmp_path


@pytest.mark.parametrize('update',[False,True])
def test_valid_after_save_context_xml_and_command(project,update):
    p=plan(update)
    validate_flow_context(p,{'objects':list(objects().values())})
    validate_record_operations(validate_flow(p.items[0].fullName,p.items[0].label,p.items[0].config),objects(),True)
    path=generate_flow(p.items[0],project)
    root=ET.parse(path).getroot()
    assert root.findtext(f'{Q("start")}/{Q("triggerType")}')=='RecordAfterSave'
    tag='recordUpdates' if update else 'recordCreates'
    node=root.find(Q(tag));assert node is not None
    assert root.find(Q('assignments')) is None
    assert root.findtext(Q('status'))=='Draft'
    assert list(root).index(node)>list(root).index(root.find(Q('processType')))
    if update:
        filters=node.findall(Q('filters'))
        assert len(filters)==2
        assert filters[0].findtext(Q('field'))=='AccountId'
        assert filters[0].findtext(f'{Q("value")}/{Q("elementReference")}')=='$Record.Id'
        assert node.findtext(Q('filterLogic'))=='and'
    else:
        assignments={n.findtext(Q('field')):n for n in node.findall(Q('inputAssignments'))}
        assert assignments['WhatId'].findtext(f'{Q("value")}/{Q("elementReference")}')=='$Record.Id'
    assert SalesforceMetadataValidator(project).validate(p)['valid']
    command=SalesforceDeploymentService(project_root=project).build_deploy_command(p,{'valid':True,'deploymentFiles':[str(path)]})
    assert command.count('--source-dir')==1


@pytest.mark.parametrize('event',['Create','Update','CreateAndUpdate'])
def test_all_save_events(event):
    c=after_config();c['recordTriggerType']=event
    assert validate_flow('Example','Example',c).recordTriggerType==event


@pytest.mark.parametrize('mutation',[
    lambda c:c.update(triggerType='RecordBeforeSave'),
    lambda c:c.update(status='Active'),
    lambda c:c.update(recordTriggerType='Delete'),
    lambda c:c['elements'][0].update(object='Account'),
    lambda c:c['elements'][0].update(next='Missing'),
    lambda c:c['elements'][0].update(faultNext='Missing'),
    lambda c:c['elements'][0].update(next='Create_Task'),
    lambda c:c['elements'][0]['inputAssignments'].append(c['elements'][0]['inputAssignments'][0]),
    lambda c:c['elements'][0]['inputAssignments'][0].update(field='Id'),
    lambda c:c['elements'][0]['inputAssignments'][1]['value'].update(value='$Record.Owner.Name'),
])
def test_rejects_invalid_operations(mutation):
    c=after_config();mutation(c)
    with pytest.raises(ValueError):validate_flow('Example','Example',c)


def test_after_save_assignment_rejected_and_before_save_retained():
    c=before_config();validate_flow('Before','Before',c)
    c['triggerType']='RecordAfterSave'
    with pytest.raises(ValueError,match='do not persist'):validate_flow('After','After',c)


def test_update_requires_relationship_scope():
    c=after_config(True);del c['elements'][0]['relationshipField']
    with pytest.raises(ValueError):validate_flow('Example','Example',c)


@pytest.mark.parametrize('mutation',[
    lambda d:d.pop('Task'),
    lambda d:d['Task'].update(createable=False),
    lambda d:d['Task']['fields'][0].update(createable=False),
    lambda d:d['Task']['fields'][0].update(calculated=True),
    lambda d:d['Task']['fields'][1].update(referenceTo=['Contact']),
    lambda d:d['Task']['fields'].append(dict(name='Required__c',type='string',createable=True,nillable=False,defaultedOnCreate=False)),
])
def test_preflight_rejects_missing_metadata_access_and_required_fields(mutation):
    d=objects();mutation(d)
    with pytest.raises(ValueError):validate_record_operations(validate_flow('Example','Example',after_config()),d,True)


def test_create_requires_related_link():
    c=after_config();c['elements'][0]['inputAssignments'].pop()
    with pytest.raises(ValueError,match='must link'):validate_record_operations(validate_flow('Example','Example',c),objects())


def test_id_reference_cannot_be_string_or_incompatible_lookup():
    c=after_config();c['elements'][0]['inputAssignments'][1]['value']={'type':'String','value':'001fake'}
    with pytest.raises(ValueError):validate_record_operations(validate_flow('Example','Example',c),objects())


def test_target_filters_and_relationship_must_be_valid():
    for field in ['Missing','Description']:
        c=after_config(True);c['elements'][0]['relationshipField']=field
        with pytest.raises(ValueError):validate_record_operations(validate_flow('Example','Example',c),objects(),True)
    d=objects();d['Contact']['fields'][2]['filterable']=False
    with pytest.raises(ValueError,match='non-filterable'):validate_record_operations(validate_flow('Example','Example',after_config(True)),d,True)


def test_source_reference_compatibility():
    c=after_config();c['elements'][0]['inputAssignments'].append({'field':'OwnerId','value':{'type':'Reference','value':'$Record.OwnerId'}})
    validate_record_operations(validate_flow('Example','Example',c),objects(),True)
    c['elements'][0]['inputAssignments'][-1]['value']['value']='$Record.Description'
    with pytest.raises(ValueError,match='lookup'):validate_record_operations(validate_flow('Example','Example',c),objects(),True)


def test_fault_connector_included_in_graph_and_xml(project):
    p=plan();c=p.items[0].config
    fallback=deepcopy(c['elements'][0]);fallback['name']='On_Failure';fallback['label']='Fallback requested by user'
    c['elements'].append(fallback);c['elements'][0]['faultNext']='On_Failure'
    path=generate_flow(p.items[0],project)
    root=ET.parse(path).getroot()
    assert root.findtext(f'{Q("recordCreates")}/{Q("faultConnector")}/{Q("targetReference")}')=='On_Failure'
    c['elements'][1]['faultNext']='Create_Task'
    with pytest.raises(ValueError,match='cycles'):validate_flow(p.items[0].fullName,p.items[0].label,c)


def test_tampered_related_record_scope_rejected(project):
    p=plan(True);path=generate_flow(p.items[0],project)
    path.write_text(path.read_text().replace('<field>AccountId</field>','<field>OwnerId</field>'))
    with pytest.raises(ValueError,match='does not match'):validate_flow_artifact(path,p.items[0],project)


def test_preflight_describes_all_objects_once():
    p=plan();d=objects();service=FlowPreflightService()
    service._cli=Mock(side_effect=lambda args:[] if args[0]=='org' else d[args[-1]])
    assert service.validate(p)['checkedFlows']==[p.items[0].fullName]
    assert service._cli.call_count==3


def test_real_http_after_save_pipeline(project,monkeypatch):
    from Backend.AI.app import main
    from Backend.AI.app.services.plan_store import PlanStore
    from Backend.AI.app.services.metadata_spec_store import MetadataSpecStore
    monkeypatch.chdir(project)
    provider=Mock();provider.generate.return_value=json.dumps(plan(status='DRAFT').model_dump())
    monkeypatch.setattr(main,'get_ai_provider',lambda:provider)
    monkeypatch.setattr(main,'plan_store',PlanStore());monkeypatch.setattr(main,'metadata_spec_store',MetadataSpecStore())
    d=objects()
    monkeypatch.setattr(FlowPreflightService,'_cli',lambda self,args:[] if args[0]=='org' else d[args[-1]])
    monkeypatch.setattr(main.PageLayoutService,'_retrieve',Mock(side_effect=AssertionError('No layouts for Flow-only')))
    def deploy(executor,plan,validation_result):
        command=executor.deployment_service.build_deploy_command(plan,validation_result)
        assert command.count('--source-dir')==1
        return {'success':True}
    monkeypatch.setattr(main.SalesforceDeploymentExecutor,'deploy',deploy)
    with TestClient(main.app) as client:
        response=client.post('/api/plan',json={'requirement':'When an Account is created create a related Task','salesforce_context':{'objects':list(d.values())}})
        assert response.status_code==200,response.text
        pid=response.json()['id']
        assert client.post(f'/api/plans/{pid}/approve').status_code==200
        response=client.post(f'/api/plans/{pid}/generate-metadata');assert response.status_code==200,response.text
        assert response.json()['metadataSpecification']['metadata'][0]['config']['triggerType']=='RecordAfterSave'
        response=client.post(f'/api/plans/{pid}/deploy');assert response.status_code==200,response.text
        assert response.json()['flowPreflight']['status']=='Draft'
        assert provider.generate.call_count==1
