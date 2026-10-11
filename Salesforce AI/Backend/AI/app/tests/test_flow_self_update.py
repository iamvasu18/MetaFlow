"""Guarded after-save triggering-record updates; Salesforce I/O is mocked."""
from copy import deepcopy
import json
from unittest.mock import Mock
import xml.etree.ElementTree as ET
import pytest
from fastapi.testclient import TestClient
from Backend.AI.app.tests.test_flow_resources import draft, context, fields
from Backend.AI.app.services.flow_formula_service import resolve_plan_formulas
from Backend.AI.app.services.flow_generator import generate_flow, validate_flow_artifact, Q
from Backend.AI.app.services.flow_preflight_service import FlowPreflightService
from Backend.AI.app.validators.flow_validator import validate_flow, validate_flow_fields, validate_record_operations
from Backend.AI.app.validators.plan_validator import ImplementationPlan


def data():
    d=context();obj=d['objects'][0];obj.update(updateable=True,createable=True)
    obj['fields'].append(dict(name='Id',type='id',filterable=True))
    obj['fields'][-2]['filterable']=True
    # Formula can be read after save without reimplementing its expression.
    obj['fields'][0]['calculatedFormula']='TODAY() - DATEVALUE(CreatedDate)'
    return d


def plan_data():
    p=draft();c=p['items'][0]['config'];c['triggerType']='RecordAfterSave'
    c['elements'][1]=dict(kind='UpdateRecords',name='Set_Description',label='Set Status Active',object='Field_List__c',relationshipField='Id',
                         inputAssignments=[dict(field='Status__c',value={'type':'String','value':'Active'})],filters=[],next=None)
    return p


def plan():
    p=plan_data();p['status']='APPROVED';p['items'][0]['approval']='APPROVED'
    return ImplementationPlan.model_validate(p)


def config(): return validate_flow('Example','Example',plan_data()['items'][0]['config'])
def objects(): return {o['name']:o for o in data()['objects']}


@pytest.fixture
def project(tmp_path):
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    return tmp_path


@pytest.mark.parametrize('event',['Create','Update','CreateAndUpdate'])
def test_same_record_supported_for_all_save_events(event):
    c=plan_data()['items'][0]['config'];c['recordTriggerType']=event
    parsed=validate_flow('Example','Example',c)
    validate_flow_fields(parsed,data()['objects'][0]['fields'],True)
    validate_record_operations(parsed,objects(),True)


def test_xml_has_id_scope_and_unchanged_value_guard(project):
    p=plan();path=generate_flow(p.items[0],project);root=ET.parse(path).getroot();node=root.find(Q('recordUpdates'))
    assert node.findtext(Q('filterLogic'))=='1 AND (2 OR 3)'
    filters=node.findall(Q('filters'))
    assert [(f.findtext(Q('field')),f.findtext(Q('operator'))) for f in filters]==[('Id','EqualTo'),('Status__c','NotEqualTo'),('Status__c','IsNull')]
    assert filters[0].findtext(f'{Q("value")}/{Q("elementReference")}')=='$Record.Id'
    assert filters[1].findtext(f'{Q("value")}/{Q("stringValue")}')=='Active'
    assert filters[2].findtext(f'{Q("value")}/{Q("booleanValue")}')=='true'
    assert root.findtext(f'.//{Q("leftValueReference")}')=='$Record.Days_of_Field__c'
    validate_flow_artifact(path,p.items[0],project)
    path.write_text(path.read_text().replace('1 AND (2 OR 3)','1'))
    with pytest.raises(ValueError,match='does not match'):validate_flow_artifact(path,p.items[0],project)


def test_multiple_fields_and_extra_filters_keep_scope(project):
    p=plan();node=p.items[0].config['elements'][1]
    node['inputAssignments'].append(dict(field='Flag__c',value={'type':'Boolean','value':True}))
    node['filters']=[dict(field='Enabled__c',operator='EqualTo',value={'type':'Boolean','value':True})]
    root=ET.parse(generate_flow(p.items[0],project)).getroot()
    assert root.findtext(f'{Q("recordUpdates")}/{Q("filterLogic")}')=='1 AND 2 AND (3 OR 4 OR 5 OR 6)'
    assert len(root.findall(f'{Q("recordUpdates")}/{Q("filters")}'))==6


@pytest.mark.parametrize('current,record_id,expected',[(None,'record1',True),('Inactive','record1',True),('Active','record1',False),('Inactive','record2',False)])
def test_generated_guard_semantics(project,current,record_id,expected):
    root=ET.parse(generate_flow(plan().items[0],project)).getroot()
    filters=root.find(Q('recordUpdates')).findall(Q('filters'))
    # Evaluate the actual emitted predicates for null, equal, different, wrong Id.
    values=[]
    for f in filters:
        field,op=f.findtext(Q('field')),f.findtext(Q('operator'))
        if field=='Id': values.append(record_id=='record1')
        elif op=='IsNull': values.append(current is None)
        else: values.append(current is not None and current!=f.findtext(f'{Q("value")}/{Q("stringValue")}'))
    assert (values[0] and (values[1] or values[2]))==expected


@pytest.mark.parametrize('mutation',[
    lambda c:c['elements'][1].update(relationshipField='Parent__c'),
    lambda c:c['elements'][1]['inputAssignments'][0].update(value={'type':'Reference','value':'$Record.Status__c'}),
    lambda c:c['elements'][1]['inputAssignments'][0].update(value={'type':'String','value':''}),
    lambda c:c['elements'][1]['inputAssignments'][0].update(value={'type':'String','value':' Active '}),
    lambda c:c['elements'][1]['inputAssignments'][0].update(field='Id'),
    lambda c:c.update(triggerType='RecordBeforeSave'),
])
def test_unsafe_self_updates_rejected(mutation):
    c=plan_data()['items'][0]['config'];mutation(c)
    with pytest.raises(ValueError):validate_flow('Example','Example',c)


def test_multiple_record_operations_rejected():
    c=plan_data()['items'][0]['config'];another=deepcopy(c['elements'][1]);another['name']='Again'
    c['elements'][1]['next']='Again';c['elements'].append(another)
    with pytest.raises(ValueError,match='only record operation'):validate_flow('Example','Example',c)


@pytest.mark.parametrize('mutation',[
    lambda o:o['Field_List__c'].update(updateable=False),
    lambda o:o['Field_List__c']['fields'][-2].update(filterable=False),
    lambda o:o['Field_List__c']['fields'][-2].update(updateable=False),
    lambda o:o['Field_List__c']['fields'][-1].update(type='string'),
    lambda o:o['Field_List__c']['fields'][-1].update(filterable=False),
])
def test_org_constraints_checked(mutation):
    o=objects();mutation(o)
    with pytest.raises(ValueError):validate_record_operations(config(),o,True)


def test_rounding_cannot_cause_repeated_updates():
    c=plan_data()['items'][0]['config'];c['elements'][1]['inputAssignments']=[dict(field='Count__c',value={'type':'Number','value':1.25})]
    o=objects();o['Field_List__c']['fields'].append(dict(name='Count__c',type='double',scale=0,updateable=True,filterable=True))
    with pytest.raises(ValueError,match='rounded'):validate_record_operations(validate_flow('Example','Example',c),o,True)
    c['elements'][1]['inputAssignments'][0]['value']['value']=1
    validate_record_operations(validate_flow('Example','Example',c),o,True)


def test_missing_id_scope_normalized_only_for_draft():
    p=plan_data();del p['items'][0]['config']['elements'][1]['relationshipField']
    result=resolve_plan_formulas(p,data())
    assert result['items'][0]['config']['elements'][1]['relationshipField']=='Id'
    assert 'relationshipField' not in p['items'][0]['config']['elements'][1]
    p['status']='APPROVED';p['items'][0]['approval']='APPROVED'
    result=resolve_plan_formulas(p,data())
    with pytest.raises(ValueError):validate_flow('Example','Example',result['items'][0]['config'])


def test_preflight_describes_trigger_object_once():
    service=FlowPreflightService();service._cli=Mock(side_effect=lambda args:[] if args[0]=='org' else objects()['Field_List__c'])
    assert service.validate(plan())['status']=='Draft'
    assert service._cli.call_count==2


def test_real_http_self_update_pipeline(project,monkeypatch):
    from Backend.AI.app import main
    from Backend.AI.app.services.plan_store import PlanStore
    from Backend.AI.app.services.metadata_spec_store import MetadataSpecStore
    monkeypatch.chdir(project);provider=Mock();provider.generate.return_value=json.dumps(plan_data())
    monkeypatch.setattr(main,'get_ai_provider',lambda:provider)
    monkeypatch.setattr(main,'plan_store',PlanStore());monkeypatch.setattr(main,'metadata_spec_store',MetadataSpecStore())
    monkeypatch.setattr(FlowPreflightService,'_cli',lambda self,args:[] if args[0]=='org' else objects()['Field_List__c'])
    monkeypatch.setattr(main.PageLayoutService,'_retrieve',Mock(side_effect=AssertionError('No layouts')))
    def deploy(executor,plan,validation_result):
        cmd=executor.deployment_service.build_deploy_command(plan,validation_result)
        xml=ET.parse(cmd[cmd.index('--source-dir')+1]).getroot()
        assert xml.findtext(f'{Q("recordUpdates")}/{Q("filterLogic")}')=='1 AND (2 OR 3)'
        return {'success':True}
    monkeypatch.setattr(main.SalesforceDeploymentExecutor,'deploy',deploy)
    with TestClient(main.app) as client:
        r=client.post('/api/plan',json={'requirement':'Create a Field List Flow to set status Active when days >= 30','salesforce_context':data()})
        assert r.status_code==200,r.text
        pid=r.json()['id'];assert client.post(f'/api/plans/{pid}/approve').status_code==200
        r=client.post(f'/api/plans/{pid}/generate-metadata');assert r.status_code==200,r.text
        r=client.post(f'/api/plans/{pid}/deploy');assert r.status_code==200,r.text
