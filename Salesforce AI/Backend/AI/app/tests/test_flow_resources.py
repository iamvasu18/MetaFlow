"""Org-derived formulas and scalar Flow resources; external I/O is mocked."""
from copy import deepcopy
import json
from types import SimpleNamespace as Obj
from unittest.mock import Mock
import xml.etree.ElementTree as ET
import pytest
from fastapi.testclient import TestClient
from Backend.AI.app.services.flow_formula_service import compile_field_formula, resolve_plan_formulas
from Backend.AI.app.services.flow_generator import generate_flow, validate_flow_artifact, Q
from Backend.AI.app.services.flow_preflight_service import FlowPreflightService
from Backend.AI.app.services.planning_service import PlanningService
from Backend.AI.app.salesforce.metadata_service import SalesforceMetadataService
from Backend.AI.app.salesforce.context_selector import SalesforceContextSelector
from Backend.AI.app.validators.flow_validator import validate_flow, validate_flow_fields, validate_record_operations
from Backend.AI.app.validators.plan_validator import ImplementationPlan
from Backend.AI.app.tests.test_flow_pipeline import plan_data
from Backend.AI.app.tests.test_flow_after_save import after_config, objects


def fields(expression='TODAY() - Start_Date__c'):
    return [
        dict(name='Days_of_Field__c',type='double',calculated=True,calculatedFormula=expression,scale=0),
        dict(name='Start_Date__c',type='date',calculated=False,createable=True,updateable=True,nillable=True),
        dict(name='CreatedDate',type='datetime',calculated=False),
        dict(name='LastModifiedDate',type='datetime',calculated=False),
        dict(name='Amount__c',type='double',calculated=False,nillable=True),
        dict(name='Status__c',type='picklist',calculated=False,createable=True,updateable=True,restrictedPicklist=True,
             picklistValues=[{'value':'Active','active':True}]),
    ]


def context(expression='TODAY() - Start_Date__c'):
    return {'objects':[{'name':'Field_List__c','label':'Field List','fields':fields(expression)}]}


def draft():
    p=plan_data('DRAFT');i=p['items'][0];c=i['config']
    i.update(fullName='Set_Status_Active',label='Set Status Active',description='Set status when days >= 30')
    c['object']='Field_List__c'
    c['elements'][0]['rules'][0]['conditions']=[dict(field='$Record.Days_of_Field__c',operator='GreaterThanOrEqualTo',value={'type':'Number','value':30})]
    c['elements'][1]['assignments']=[dict(field='$Record.Status__c',value={'type':'String','value':'Active'})]
    return p


def resolved(): return resolve_plan_formulas(draft(),context())
def config(): return validate_flow('Set_Status_Active','Set Status Active',resolved()['items'][0]['config'])
def approved():
    p=resolved();p['status']='APPROVED';p['items'][0]['approval']='APPROVED'
    return ImplementationPlan.model_validate(p)


@pytest.fixture
def project(tmp_path):
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    return tmp_path


def test_automatic_days_resource_without_variable_or_ai_formula():
    original=draft();before=deepcopy(original)
    p=resolve_plan_formulas(original,context());c=p['items'][0]['config']
    assert original==before
    assert c['elements'][0]['rules'][0]['conditions'][0]['field']=='Formula_1'
    assert c['formulas'][0]['expression']=='(TODAY() - {!$Record.Start_Date__c})'
    assert c['formulas'][0]['dataType']=='Number' and 'variables' not in c
    assert resolve_plan_formulas(p,context())==p
    validate_flow_fields(config(),fields(),True)


def test_planning_retrieves_and_preserves_formula_dependencies():
    service=SalesforceMetadataService('AIOrg')
    service._run_sf_command=Mock(return_value={'result':context()['objects'][0]})
    service.get_field_definitions=Mock(return_value=[])
    service.find_relevant_objects=Mock(return_value=['Field_List__c'])
    provider=Mock();provider.generate.return_value=json.dumps(draft())
    p=PlanningService(provider,service).generate_plan('Create a Field List Flow setting status when days >= 30')
    assert p.items[0].config['formulas'][0]['sourceField']=='Days_of_Field__c'
    prompt=provider.generate.call_args.kwargs['user_prompt']
    assert 'calculatedFormula' in prompt and 'Start_Date__c' in prompt
    assert service._run_sf_command.call_count==1
    assert SalesforceContextSelector().select('Field List',context())['objects'][0]['fields']==fields()


def test_formula_xml_reference_and_order(project):
    item=approved().items[0];path=generate_flow(item,project);root=ET.parse(path).getroot()
    assert root.findtext(f'{Q("formulas")}/{Q("expression")}')=='(TODAY() - {!$Record.Start_Date__c})'
    assert root.findtext(f'.//{Q("leftValueReference")}')=='Formula_1'
    assert '$Record.Days_of_Field__c' not in path.read_text()
    tags=[node.tag.split('}')[1] for node in root]
    assert tags.index('description')<tags.index('formulas')<tags.index('interviewLabel')
    validate_flow_artifact(path,item,project)
    path.write_text(path.read_text().replace('TODAY()', 'NOW()'))
    with pytest.raises(ValueError,match='does not match'):validate_flow_artifact(path,item,project)


@pytest.mark.parametrize('expression',[
    'Parent__r.Start_Date__c', '$User.Id', 'Unknown__c + 1',
    'TODAY(1)', 'DATEVALUE(Start_Date__c)', 'TODAY() + "bad"',
    'TODAY() -', 'TODAY(); NOW()', 'IMAGE("x", "x")',
    'Amount__c + 1', 'TODAY() - DATEVALUE(CreatedDate)',
    'TODAY() - DATEVALUE(LastModifiedDate)', '(' * 45 + '1' + ')' * 45,
])
def test_unsupported_or_unavailable_formulas_fail_during_planning(expression):
    with pytest.raises(ValueError):resolve_plan_formulas(draft(),context(expression))


def test_created_date_update_only_preserves_expression():
    p=draft();p['items'][0]['config']['recordTriggerType']='Update'
    r=resolve_plan_formulas(p,context('TODAY() - DATEVALUE(CreatedDate)'))
    assert 'DATEVALUE({!$Record.CreatedDate})' in r['items'][0]['config']['formulas'][0]['expression']


def test_nested_formulas_and_cycles():
    data=fields('Nested__c + 1');data.append(dict(name='Nested__c',type='double',calculated=True,calculatedFormula='TODAY() - Start_Date__c',scale=0))
    result=compile_field_formula('Days_of_Field__c',data,Obj(**draft()['items'][0]['config']))
    assert 'Nested__c' not in result['expression'] and 'Start_Date__c' in result['expression']
    data[-1]['calculatedFormula']='Days_of_Field__c'
    with pytest.raises(ValueError,match='Cyclic'):compile_field_formula('Days_of_Field__c',data,Obj(**draft()['items'][0]['config']))


def test_string_literals_are_not_rewritten():
    data=fields();data[0].update(type='string',calculatedFormula='"Start_Date__c & <tag>"',scale=0)
    result=compile_field_formula('Days_of_Field__c',data,Obj(**draft()['items'][0]['config']))
    assert result['expression']=='"Start_Date__c & <tag>"'


@pytest.mark.parametrize('expression,typ',[
    ('IF(ISBLANK(Start_Date__c), 0, TODAY() - Start_Date__c)','double'),
    ('AND(TODAY() > Start_Date__c, NOT(FALSE))','boolean'),
    ('DATE(2026, 1, 1)','date'), ('NOW()','datetime'), ('"hello" & "world"','string'),
])
def test_typed_functions(expression,typ):
    data=fields(expression);data[0]['type']=typ
    assert compile_field_formula('Days_of_Field__c',data,Obj(**draft()['items'][0]['config']))['expression']


def test_formula_scale_and_missing_definition():
    for mutation in [dict(scale=None),dict(calculatedFormula=None),dict(type='boolean')]:
        data=fields();data[0].update(mutation)
        with pytest.raises(ValueError):compile_field_formula('Days_of_Field__c',data,Obj(**draft()['items'][0]['config']))


def test_raw_calculated_reference_cannot_bypass_resolver():
    c=validate_flow('Example','Example',draft()['items'][0]['config'])
    with pytest.raises(ValueError,match='resolved Flow formula'):validate_flow_fields(c,fields())


@pytest.mark.parametrize('change',[
    lambda f:f[0].update(calculatedFormula='TODAY() - Start_Date__c + 1'),
    lambda f:f[0].update(scale=2), lambda f:f[1].update(type='datetime'), lambda f:f.pop(1),
])
def test_fresh_preflight_detects_source_or_dependency_drift(change):
    data=fields();change(data);service=FlowPreflightService()
    service._cli=Mock(side_effect=lambda args:[] if args[0]=='org' else {'fields':data})
    with pytest.raises(ValueError):service.validate(approved())


def test_resource_name_collision_and_formula_reuse():
    p=draft();c=p['items'][0]['config'];c['variables']=[dict(name='Formula_1',dataType='Number',value={'type':'Number','value':0})]
    condition=c['elements'][0]['rules'][0]['conditions'][0];c['elements'][0]['rules'][0]['conditions'].append(deepcopy(condition))
    r=resolve_plan_formulas(p,context())['items'][0]['config']
    assert len(r['formulas'])==1 and r['formulas'][0]['name']=='Formula_2'


def test_variable_stores_formula_value_and_drives_decision(project):
    p=resolved();c=p['items'][0]['config']
    c['variables']=[dict(name='DaysValue',dataType='Number',scale=0,value={'type':'Number','value':0})]
    c['elements'].insert(0,dict(kind='Assignment',name='Store_Days',label='Store days',next=c['startElement'],assignments=[dict(field='DaysValue',value={'type':'Reference','value':'Formula_1'})]))
    c['startElement']='Store_Days';c['elements'][1]['rules'][0]['conditions'][0]['field']='DaysValue'
    validate_flow_fields(validate_flow('Example','Example',c),fields(),True)
    root=ET.parse(generate_flow(ImplementationPlan.model_validate(p).items[0],project)).getroot()
    assert root.findtext(f'{Q("variables")}/{Q("name")}')=='DaysValue'
    assert root.findtext(f'.//{Q("elementReference")}')=='Formula_1'
    assert root[-1].tag==Q('variables')


def test_assignment_read_formula_resolved_automatically():
    p=draft();c=p['items'][0]['config'];c['variables']=[dict(name='DaysValue',dataType='Number',value={'type':'Number','value':0})]
    c['elements'][1]['assignments'].append(dict(field='DaysValue',value={'type':'Reference','value':'$Record.Days_of_Field__c'}))
    r=resolve_plan_formulas(p,context())['items'][0]['config']
    assert r['elements'][1]['assignments'][1]['value']['value']=='Formula_1'


@pytest.mark.parametrize('mutate',[
    lambda c:c['elements'][0]['rules'][0]['conditions'][0].update(field='Unknown'),
    lambda c:c['elements'][1]['assignments'][0].update(field='Formula_1'),
    lambda c:c.update(variables=[dict(name='Formula_1',dataType='Number',value={'type':'Number','value':0})]),
    lambda c:c.update(variables=[dict(name='NumberVar',dataType='Number',value={'type':'String','value':'bad'})]),
    lambda c:c['elements'][1]['assignments'][0].update(value={'type':'Reference','value':'Unknown'}),
])
def test_invalid_resource_graph_rejected(mutate):
    c=resolved()['items'][0]['config'];mutate(c)
    with pytest.raises(ValueError):validate_flow('Example','Example',c)


def test_wrong_reference_type_rejected():
    c=resolved()['items'][0]['config'];c['elements'][1]['assignments'][0]['value']={'type':'Reference','value':'Formula_1'}
    with pytest.raises(ValueError,match='type'):validate_flow_fields(validate_flow('Example','Example',c),fields())


def test_after_save_record_input_variable_supported():
    c=after_config();c['variables']=[dict(name='SubjectValue',dataType='String',value={'type':'String','value':'Follow up'})]
    c['elements'][0]['inputAssignments'][0]['value']={'type':'Reference','value':'SubjectValue'}
    validate_record_operations(validate_flow('Example','Example',c),objects(),True)


def test_approved_formula_cannot_be_rewritten_by_ai():
    p=approved().model_dump();p['items'][0]['config']['formulas'][0]['expression']='999'
    with pytest.raises(ValueError,match='differs'):resolve_plan_formulas(p,context())


def test_real_http_formula_plan_to_draft_deploy(project,monkeypatch):
    from Backend.AI.app import main
    from Backend.AI.app.services.plan_store import PlanStore
    from Backend.AI.app.services.metadata_spec_store import MetadataSpecStore
    monkeypatch.chdir(project)
    provider=Mock();provider.generate.return_value=json.dumps(draft())
    monkeypatch.setattr(main,'get_ai_provider',lambda:provider)
    monkeypatch.setattr(main,'plan_store',PlanStore());monkeypatch.setattr(main,'metadata_spec_store',MetadataSpecStore())
    monkeypatch.setattr(FlowPreflightService,'_cli',lambda self,args:[] if args[0]=='org' else {'fields':fields()})
    monkeypatch.setattr(main.PageLayoutService,'_retrieve',Mock(side_effect=AssertionError('No layouts for Flow-only')))
    def deploy(executor,plan,validation_result):
        command=executor.deployment_service.build_deploy_command(plan,validation_result)
        assert command.count('--source-dir')==1
        assert ET.parse(command[command.index('--source-dir')+1]).find(f'.//{Q("formulas")}') is not None
        return {'success':True}
    monkeypatch.setattr(main.SalesforceDeploymentExecutor,'deploy',deploy)
    with TestClient(main.app) as client:
        response=client.post('/api/plan',json={'requirement':'Create a Flow on Field List when days >= 30 set status Active','salesforce_context':context()})
        assert response.status_code==200,response.text
        assert response.json()['items'][0]['config']['formulas'][0]['sourceField']=='Days_of_Field__c'
        pid=response.json()['id'];assert client.post(f'/api/plans/{pid}/approve').status_code==200
        response=client.post(f'/api/plans/{pid}/generate-metadata');assert response.status_code==200,response.text
        response=client.post(f'/api/plans/{pid}/deploy');assert response.status_code==200,response.text
        assert provider.generate.call_count==1


def test_formula_schema_matches_current_runtime():
    from pathlib import Path
    from Backend.AI.app.validators.flow_validator import flow_config_json_schema
    root=Path(__file__).resolve().parents[4]
    saved=json.loads((root/'Prompt Engineering/Schemas/flow-config-v001.json').read_text())
    saved.pop('$schema')
    assert saved==flow_config_json_schema()


def test_comparison_reference_and_variable_after_save_assignment():
    c=resolved()['items'][0]['config']
    c['variables']=[dict(name='Threshold',dataType='Number',value={'type':'Number','value':30})]
    c['elements'][0]['rules'][0]['conditions'][0]['value']={'type':'Reference','value':'Threshold'}
    validate_flow_fields(validate_flow('Example','Example',c),fields())
    c=after_config();c['variables']=[dict(name='SubjectValue',dataType='String',value={'type':'String','value':'Initial'})]
    c['elements'].insert(0,dict(kind='Assignment',name='Set_Subject',label='Set subject',next=c['startElement'],assignments=[dict(field='SubjectValue',value={'type':'String','value':'Follow up'})]))
    c['startElement']='Set_Subject'
    c['elements'][1]['inputAssignments'][0]['value']={'type':'Reference','value':'SubjectValue'}
    parsed=validate_flow('Example','Example',c)
    validate_flow_fields(parsed,objects()['Account']['fields'])
    validate_record_operations(parsed,objects(),True)


def test_unrelated_formula_change_does_not_invalidate_plan():
    data=fields();data.append(dict(name='Unused__c',type='double',calculated=True,calculatedFormula='99',scale=0))
    validate_flow_fields(config(),data,True)


def test_preflight_refuses_tampered_formula_even_with_original_fingerprint():
    p=approved();p.items[0].config['formulas'][0]['expression']='30'
    service=FlowPreflightService();service._cli=Mock(side_effect=lambda args:[] if args[0]=='org' else {'fields':fields()})
    with pytest.raises(ValueError,match='altered'):service.validate(p)


def test_nested_formula_does_not_introduce_rounding():
    data=fields('Nested__c * 10');data.append(dict(name='Nested__c',type='double',calculated=True,calculatedFormula='1 / 3',scale=0))
    result=compile_field_formula('Days_of_Field__c',data,Obj(**draft()['items'][0]['config']))
    assert result['expression']=='((1 / 3) * 10)'


@pytest.mark.parametrize('trigger', ['RecordBeforeSave', 'RecordAfterSave'])
@pytest.mark.parametrize('source', ['Days_of_Field__c', 'Field_List__c.Days_of_Field__c', '$Record.Days_of_Field__c'])
def test_draft_placeholder_formula_is_rebuilt_from_org(trigger, source):
    p=draft();c=p['items'][0]['config'];c['triggerType']=trigger
    c['formulas']=[dict(name='DaysFormula',sourceField=source,dataType='String',expression='999',
                        scale=12,sourceFingerprint='calculated_field_dependency')]
    c['elements'][0]['rules'][0]['conditions'][0]['field']='DaysFormula'
    before=deepcopy(p)
    r=resolve_plan_formulas(p,context())['items'][0]['config']['formulas'][0]
    assert p==before
    assert r['sourceField']=='Days_of_Field__c' and r['dataType']=='Number'
    assert r['expression']=='(TODAY() - {!$Record.Start_Date__c})'
    assert len(r['sourceFingerprint'])==64 and r['scale']==0


def test_planning_rebuilds_placeholder_before_pydantic_validation():
    p=draft();c=p['items'][0]['config']
    c['formulas']=[dict(name='DaysFormula',sourceField='Field_List__c.Days_of_Field__c',
                        sourceFingerprint='calculated_field_dependency')]
    c['elements'][0]['rules'][0]['conditions'][0]['field']='DaysFormula'
    provider=Mock();provider.generate.return_value=json.dumps(p)
    result=PlanningService(provider).generate_plan('Create a Flow on Field List',salesforce_context=context())
    assert result.items[0].config['formulas'][0]['dataType']=='Number'


def test_draft_formula_wrong_object_is_not_normalized():
    p=draft();p['items'][0]['config']['formulas']=[dict(name='DaysFormula',sourceField='Other__c.Days_of_Field__c')]
    with pytest.raises(ValueError,match='triggering object'):resolve_plan_formulas(p,context())
