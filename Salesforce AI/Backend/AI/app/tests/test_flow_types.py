"""Additional Flow families: contracts, org checks, metadata and HTTP deployment."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock
import xml.etree.ElementTree as ET
import pytest
from fastapi.testclient import TestClient
from Backend.AI.app.validators.flow_validator import validate_flow, validate_flow_context, flow_objects
from Backend.AI.app.validators.flow_validator import (
    validate_extended_context,
    Schedule,
)
from Backend.AI.app.validators.plan_validator import ImplementationPlan
from Backend.AI.app.services.flow_generator import generate_flow, validate_flow_artifact, Q
from Backend.AI.app.services.flow_preflight_service import FlowPreflightService
from Backend.AI.app.services.planning_service import PlanningService
from Backend.AI.app.services.flow_formula_service import resolve_plan_formulas
from Backend.AI.app.tests.test_flow_pipeline import plan_data as legacy_plan


def literal(value):
    return {'type':'Boolean' if type(value) is bool else 'Number' if type(value) in (int,float) else 'String','value':value}

def ref(name):return {'type':'Reference','value':name}

def field(name,typ='string',**kw):
    return dict(name=name,type=typ,createable=True,updateable=True,filterable=True,sortable=True,nillable=True,
                calculated=False,autoNumber=False,defaultedOnCreate=False,**kw)


def context():
    objects=[]
    for name in ['Account','Audit__c']:
        objects.append(dict(name=name,label=name,createable=True,updateable=True,queryable=True,fields=[
            field('Id','id'),field('Name',length=255),field('Description','textarea',length=32000),field('Deleted_Name__c',length=255)]))
    objects.append(dict(name='Notice__e',label='Notice',createable=True,updateable=False,queryable=False,
                        fields=[field('Message__c'),field('AccountId__c')]))
    return {'orgTimeZone':'UTC','objects':objects}


def configs(kind):
    base=dict(flowType=kind,status='Draft',startElement='Start_Work',variables=[],elements=[])
    if kind=='Screen':
        base['elements']=[dict(kind='Screen',name='Start_Work',label='Enter account name',fields=[dict(name='AccountName',fieldType='InputField',fieldText='Account name',dataType='String',isRequired=True)],next='Create_Account'),
                          dict(kind='CreateRecords',name='Create_Account',label='Create account',object='Account',inputAssignments=[dict(field='Name',value=ref('AccountName'))],next=None)]
    elif kind=='Autolaunched':
        base['variables']=[dict(name='accountId',dataType='String',referenceTo='Account',isInput=True),dict(name='foundId',dataType='String',referenceTo='Account',isOutput=True),dict(name='description',dataType='String',isInput=True)]
        base['elements']=[dict(kind='GetRecords',name='Start_Work',label='Find account',object='Account',filters=[dict(field='Id',operator='EqualTo',value=ref('accountId'))],outputAssignments=[dict(field='Id',variable='foundId')],next='Check_Found'),
                          dict(kind='Decision',name='Check_Found',label='Account found',defaultLabel='No account',defaultNext=None,rules=[dict(name='Found',label='Found',conditionLogic='and',conditions=[dict(field='foundId',operator='IsNull',value=literal(False))],next='Update_Account')]),
                          dict(kind='UpdateRecordById',name='Update_Account',label='Update account',object='Account',recordId=ref('foundId'),inputAssignments=[dict(field='Description',value=ref('description'))],next=None)]
    elif kind=='Scheduled':
        base.update(triggerType='Scheduled',object='Account',schedule=dict(frequency='Daily',startDate='2099-01-01',startTime='09:00:00',timeZone='UTC'),startFilters=[dict(field='Name',operator='EqualTo',value=literal('Scheduled Test'))])
        base['elements']=[dict(kind='UpdateRecordById',name='Start_Work',label='Update scheduled account',object='Account',recordId=ref('$Record.Id'),inputAssignments=[dict(field='Description',value=literal('Reviewed'))],next=None)]
    elif kind=='PlatformEvent':
        base.update(triggerType='PlatformEvent',object='Notice__e')
        base['elements']=[dict(kind='CreateRecords',name='Start_Work',label='Create audit record',object='Audit__c',inputAssignments=[dict(field='Name',value=ref('$Record.Message__c'))],next=None)]
    else:
        base.update(flowType='RecordTriggered',triggerType='RecordBeforeDelete',recordTriggerType='Delete',object='Account')
        base['elements']=[dict(kind='CreateRecords',name='Start_Work',label='Audit account deletion',object='Audit__c',inputAssignments=[dict(field='Name',value=literal('Account deleted')),dict(field='Deleted_Name__c',value=ref('$Record.Name'))],next=None)]
    return base


def plan_data(kind,status='APPROVED'):
    p=legacy_plan(status);p['items'][0].update(fullName='Example_'+kind,label='Example '+kind,config=configs(kind));return p

def plan(kind):return ImplementationPlan.model_validate(plan_data(kind))

def parsed(kind):return validate_flow('Example','Example',configs(kind))

def objects():return {o['name']:o for o in context()['objects']}


@pytest.fixture
def project(tmp_path):
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    return tmp_path


@pytest.mark.parametrize('kind',['Screen','Autolaunched','Scheduled','PlatformEvent','Delete'])
def test_contract_context_and_fresh_org_validation(kind):
    validate_flow_context(plan(kind),context())
    validate_extended_context(parsed(kind),objects(),True,'UTC')


@pytest.mark.parametrize('kind',['Screen','Autolaunched','Scheduled','PlatformEvent','Delete'])
def test_each_type_xml_start_and_draft(project,kind):
    item=plan(kind).items[0];path=generate_flow(item,project);root=ET.parse(path).getroot()
    assert root.findtext(Q('status'))=='Draft'
    assert root.findtext(Q('processType'))==('Flow' if kind=='Screen' else 'AutoLaunchedFlow')
    start=root.find(Q('start'))
    expected={'Screen':None,'Autolaunched':None,'Scheduled':'Scheduled','PlatformEvent':'PlatformEvent','Delete':'RecordBeforeDelete'}[kind]
    assert start.findtext(Q('triggerType'))==expected
    assert start.findtext(Q('recordTriggerType'))==('Delete' if kind=='Delete' else None)
    if kind in {'Screen','Autolaunched'}:assert start.find(Q('object')) is None
    if kind=='Scheduled':assert start.findtext(f'{Q("schedule")}/{Q("startTime")}')=='09:00:00.000Z'
    validate_flow_artifact(path,item,project)
    path.write_text(path.read_text().replace('<status>Draft</status>','<status>Active</status>'))
    with pytest.raises(ValueError):validate_flow_artifact(path,item,project)


def test_screen_input_and_create_reference(project):
    root=ET.parse(generate_flow(plan('Screen').items[0],project)).getroot()
    screen=root.find(Q('screens'))
    assert screen.findtext(f'{Q("fields")}/{Q("fieldType")}')=='InputField'
    assert root.findtext(f'{Q("recordCreates")}/{Q("inputAssignments")}/{Q("value")}/{Q("elementReference")}')=='AccountName'
    assert screen.findtext(Q('allowBack'))=='false'


def test_autolaunched_get_and_single_id_update(project):
    root=ET.parse(generate_flow(plan('Autolaunched').items[0],project)).getroot()
    get=root.find(Q('recordLookups'));update=root.find(Q('recordUpdates'))
    assert get.findtext(Q('getFirstRecordOnly'))=='true'
    assert get.findtext(Q('sortField'))=='Id'
    assert get.findtext(Q('assignNullValuesIfNoRecordsFound'))=='true'
    assert update.findtext(f'{Q("filters")}/{Q("field")}')=='Id'
    assert update.findtext(f'{Q("filters")}/{Q("value")}/{Q("elementReference")}')=='foundId'
    assert len(update.findall(Q('filters')))==1
    vars={v.findtext(Q('name')):v for v in root.findall(Q('variables'))}
    assert vars['accountId'].findtext(Q('isInput'))=='true'
    assert vars['foundId'].findtext(Q('isOutput'))=='true'


@pytest.mark.parametrize('frequency',['Once','Daily','Weekly'])
def test_schedule_frequencies_and_timezone_conversion(frequency):
    s=Schedule(frequency=frequency,startDate='2099-01-01',startTime='01:00:00',timeZone='Asia/Kolkata')
    assert s.utc_start().strftime('%Y-%m-%d %H:%M:%S')=='2098-12-31 19:30:00'


@pytest.mark.parametrize('changes',[
    dict(startDate='2099-02-30'),dict(startTime='25:00:00'),dict(timeZone='Invented/Zone'),dict(frequency='Hourly'),
    dict(startDate='2026-03-08',startTime='02:30:00',timeZone='America/New_York'),
    dict(startDate='2026-11-01',startTime='01:30:00',timeZone='America/New_York'),
])
def test_invalid_or_ambiguous_schedule_rejected(changes):
    c=configs('Scheduled')['schedule'];c.update(changes)
    with pytest.raises(ValueError):Schedule.model_validate(c)


def test_schedule_timezone_drift_and_past_start_rejected():
    with pytest.raises(ValueError,match='time zone'):validate_extended_context(parsed('Scheduled'),objects(),True,'Asia/Kolkata')
    c=configs('Scheduled');c['schedule']['startDate']='2000-01-01'
    with pytest.raises(ValueError,match='past'):validate_extended_context(validate_flow('Example','Example',c),objects(),True,'UTC')


def test_objectless_screen_and_autolaunched_work_without_org_objects():
    c=configs('Screen');c['elements']=c['elements'][:1];c['elements'][0]['next']=None
    p=validate_flow('Example','Example',c);assert flow_objects(p)==set();validate_extended_context(p,{})
    c=dict(flowType='Autolaunched',status='Draft',startElement='Set_Result',variables=[dict(name='result',dataType='String',isOutput=True)],elements=[dict(kind='Assignment',name='Set_Result',label='Set result',assignments=[dict(field='result',value=literal('Done'))],next=None)])
    validate_extended_context(validate_flow('Example','Example',c),{})


@pytest.mark.parametrize('kind,mutation',[
    ('Screen',lambda c:c.update(object='Account')),
    ('Screen',lambda c:c.update(triggerType='RecordAfterSave')),
    ('Screen',lambda c:c['elements'][0]['fields'][0].update(fieldText='<script>bad</script>')),
    ('Screen',lambda c:c.update(startElement='Create_Account')),
    ('Autolaunched',lambda c:c['elements'][2].update(recordId=literal('001fake'))),
    ('Autolaunched',lambda c:c['elements'][0].update(filters=[])),
    ('Autolaunched',lambda c:c['elements'][2]['inputAssignments'][0].update(value=ref('$Record.Name'))),
    ('Scheduled',lambda c:c.update(startFilters=[])),
    ('Scheduled',lambda c:c.update(schedule=None)),
    ('PlatformEvent',lambda c:c.update(object='Account')),
    ('PlatformEvent',lambda c:c['elements'][0].update(object='Notice__e')),
    ('Delete',lambda c:c.update(recordTriggerType='Update')),
    ('Delete',lambda c:c['elements'][0].update(object='Account')),
    ('Delete',lambda c:c['elements'][0].update(next='Start_Work')),
])
def test_invalid_type_graph_and_scope(kind,mutation):
    c=configs(kind);mutation(c)
    with pytest.raises(ValueError):validate_flow('Example','Example',c)


def test_screen_resource_must_dominate_use():
    c=configs('Screen');screen=c['elements'][0];screen['next']='Create_Account'
    c['variables']=[dict(name='flag',dataType='Boolean',value=literal(True))]
    c['elements'].insert(0,dict(kind='Decision',name='Branch',label='Branch',defaultLabel='Skip screen',defaultNext='Create_Account',rules=[dict(name='Enter',label='Enter',conditionLogic='and',conditions=[dict(field='flag',operator='EqualTo',value=literal(True))],next='Start_Work')]))
    c['startElement']='Branch'
    with pytest.raises(ValueError,match='before its screen'):validate_flow('Example','Example',c)


@pytest.mark.parametrize('mutation',[
    lambda o:o['Account'].update(updateable=False),
    lambda o:o['Account'].update(queryable=False),
    lambda o:o['Account']['fields'][0].update(sortable=False),
    lambda o:o['Account']['fields'][0].update(filterable=False),
    lambda o:o['Account']['fields'][2].update(updateable=False),
    lambda o:o['Account']['fields'].pop(2),
])
def test_org_read_write_constraints(mutation):
    o=objects();mutation(o)
    with pytest.raises(ValueError):validate_extended_context(parsed('Autolaunched'),o,True)


def test_typed_id_must_match_update_object():
    c=configs('Autolaunched');c['variables'][1]['referenceTo']='Audit__c'
    with pytest.raises(ValueError,match='Id object types'):validate_extended_context(validate_flow('Example','Example',c),objects())


def test_delete_cannot_retain_lookup_to_deleted_object():
    c=configs('Delete');c['elements'][0]['inputAssignments'].append(dict(field='Account__c',value=ref('$Record.Id')))
    o=objects();o['Audit__c']['fields'].append(field('Account__c','reference',referenceTo=['Account']))
    with pytest.raises(ValueError,match='being deleted'):validate_extended_context(validate_flow('Example','Example',c),o,True)


def test_platform_event_text_id_to_declared_typed_variable():
    c=configs('PlatformEvent');c['variables']=[dict(name='accountId',dataType='String',referenceTo='Account')]
    c['elements']=[dict(kind='Assignment',name='Start_Work',label='Read event account ID',assignments=[dict(field='accountId',value=ref('$Record.AccountId__c'))],next='Update_Account'),dict(kind='UpdateRecordById',name='Update_Account',label='Update account',object='Account',recordId=ref('accountId'),inputAssignments=[dict(field='Description',value=ref('$Record.Message__c'))],next=None)]
    validate_extended_context(validate_flow('Example','Example',c),objects(),True)


@pytest.mark.parametrize('kind',['Screen','Autolaunched','Scheduled','PlatformEvent','Delete'])
def test_preflight_describes_referenced_objects_once(kind):
    service=FlowPreflightService();o=objects()
    service._cli=Mock(side_effect=lambda args:[] if args[0]=='org' else {'records':[{'TimeZoneSidKey':'UTC'}]} if args[0]=='data' else o[args[-1]])
    service.validate(plan(kind))
    assert service._cli.call_count==1+len(flow_objects(parsed(kind)))+(1 if kind=='Scheduled' else 0)


def test_planning_retrieves_org_timezone_before_prompt():
    metadata=Mock();metadata.find_relevant_objects.return_value=['Account'];metadata.get_context.return_value={'objects':[objects()['Account']]};metadata.get_org_timezone.return_value='UTC'
    provider=Mock();provider.generate.return_value=json.dumps(plan_data('Scheduled','DRAFT'))
    result=PlanningService(provider,metadata).generate_plan('Create a daily scheduled Flow on Account')
    assert result.items[0].config['schedule']['timeZone']=='UTC'
    metadata.get_org_timezone.assert_called_once()
    assert 'orgTimeZone' in provider.generate.call_args.kwargs['user_prompt']


def test_planning_retries_untyped_record_id_with_object_reference():
    good = plan_data('Autolaunched', 'DRAFT')
    bad = deepcopy(good)
    bad['items'][0]['config']['variables'][0].pop('referenceTo')
    provider = Mock()
    provider.generate.side_effect = [json.dumps(bad), json.dumps(good)]

    result = PlanningService(provider).generate_plan(
        'Create an Autolaunched Flow to find and update an Account by Id.',
        context(),
    )

    assert result.items[0].config['variables'][0]['referenceTo'] == 'Account'
    assert provider.generate.call_count == 2
    retry_prompt = provider.generate.call_args.kwargs['system_prompt']
    assert 'dataType String' in retry_prompt
    assert 'referenceTo' in retry_prompt


@pytest.mark.parametrize('kind',['Screen','Autolaunched','Scheduled','PlatformEvent','Delete'])
def test_real_http_pipeline_all_new_types(project,monkeypatch,kind):
    from Backend.AI.app import main
    from Backend.AI.app.services.plan_store import PlanStore
    from Backend.AI.app.services.metadata_spec_store import MetadataSpecStore
    monkeypatch.chdir(project);provider=Mock();provider.generate.return_value=json.dumps(plan_data(kind,'DRAFT'))
    monkeypatch.setattr(main,'get_ai_provider',lambda:provider)
    monkeypatch.setattr(main,'plan_store',PlanStore());monkeypatch.setattr(main,'metadata_spec_store',MetadataSpecStore())
    monkeypatch.setattr(FlowPreflightService,'_cli',lambda self,args:[] if args[0]=='org' else {'records':[{'TimeZoneSidKey':'UTC'}]} if args[0]=='data' else objects()[args[-1]])
    monkeypatch.setattr(FlowPreflightService,'validate_generated',lambda *a,**k: {'required':True,'success':True})
    monkeypatch.setattr(main.PageLayoutService,'_retrieve',Mock(side_effect=AssertionError('No layouts for Flow-only plans')))
    def deploy(executor,plan,validation_result):
        cmd=executor.deployment_service.build_deploy_command(plan,validation_result)
        assert cmd.count('--source-dir')==1
        root=ET.parse(cmd[cmd.index('--source-dir')+1]).getroot();assert root.findtext(Q('status'))=='Draft'
        return {'success':True}
    monkeypatch.setattr(main.SalesforceDeploymentExecutor,'deploy',deploy)
    with TestClient(main.app) as client:
        result=client.post('/api/plan',json={'requirement':f'Create {kind} Flow using Account Audit__c Notice__e','salesforce_context':context()})
        assert result.status_code==200,result.text
        pid=result.json()['id'];assert client.post(f'/api/plans/{pid}/approve').status_code==200
        result=client.post(f'/api/plans/{pid}/generate-metadata');assert result.status_code==200,result.text
        result=client.post(f'/api/plans/{pid}/deploy');assert result.status_code==200,result.text
        assert provider.generate.call_count==1

# Integrated resource/element contract regression tests.
from Backend.AI.app.validators.flow_validator import FlowValue, ExtendedFlowConfig, flow_config_json_schema
from Backend.AI.app.services.flow_generator import flow_xml
from types import SimpleNamespace


def resource_config():
    return dict(flowType='Autolaunched',status='Draft',startElement='Set_Value',
        variables=[dict(name='result',dataType='String',isOutput=True)],
        elements=[dict(kind='Assignment',name='Set_Value',label='Set value',assignments=[dict(field='result',value=literal('Done'))],next=None)])


def checked_config(c,ctx=None):
    parsed=validate_flow('Integrated_Test','Integrated Test',c)
    validate_extended_context(parsed,objects() if ctx is None else ctx,True,'UTC')
    item=SimpleNamespace(fullName='Integrated_Test',label='Integrated Test',description=None,config=c)
    return flow_xml(item,'67.0')


@pytest.mark.parametrize('datatype,fieldtype,value,tag',[
    ('String','string','Sample','stringValue'),('Number','double',10,'numberValue'),
    ('Currency','currency',12.5,'numberValue'),('Boolean','boolean',False,'booleanValue'),
    ('Date','date','2026-10-07','dateValue'),('DateTime','datetime','2026-10-07T09:00:00Z','dateTimeValue')])
def test_screen_typed_defaults_and_record_mapping(datatype,fieldtype,value,tag):
    c=configs('Screen');screen=c['elements'][0]['fields'][0];screen.update(dataType=datatype,defaultValue=dict(type='Number' if datatype=='Currency' else datatype,value=value))
    c['elements'][1]['inputAssignments'][0]['field']='Typed_Field__c'
    ctx=objects();ctx['Account']['fields'].append(field('Typed_Field__c',fieldtype))
    xml=checked_config(c,ctx)
    assert xml.findtext(f'{Q("screens")}/{Q("fields")}/{Q("defaultValue")}/{Q(tag)}')==('false' if value is False else str(value))


@pytest.mark.parametrize('type_,value',[('Date','2026-02-30'),('Date','07/10/2026'),('DateTime','2026-10-07'),('DateTime','2026-10-07T09:00:00'),('Number','20')])
def test_bad_temporal_and_numeric_literals(type_,value):
    with pytest.raises(ValueError):FlowValue(type=type_,value=value)


@pytest.mark.parametrize('control',['DropdownBox','RadioButtons','MultiSelectCheckboxes','MultiSelectPicklist'])
def test_screen_choice_controls(control):
    c=configs('Screen');c['choices']=[dict(name='Choice_Active',choiceText='Active',dataType='String',value=literal('Active'))]
    c['elements'][0]['fields'][0].update(fieldType=control,choiceReferences=['Choice_Active'],defaultSelectedChoiceReference='Choice_Active')
    xml=checked_config(c)
    assert xml.findtext(f'{Q("screens")}/{Q("fields")}/{Q("choiceReferences")}')=='Choice_Active'
    assert xml.findtext(f'{Q("choices")}/{Q("value")}/{Q("stringValue")}')=='Active'


@pytest.mark.parametrize('control',['LargeTextArea','PasswordField'])
def test_additional_text_controls(control):
    c=configs('Screen');c['elements'][0]['fields'][0]['fieldType']=control
    assert checked_config(c).findtext(f'{Q("screens")}/{Q("fields")}/{Q("fieldType")}')==control


def test_screen_validation_visibility_navigation_xml():
    c=configs('Screen');c['variables']=[dict(name='showName',dataType='Boolean',value=literal(True))]
    c['elements'][0].update(allowBack=True,nextOrFinishButtonLabel='Save',backButtonLabel='Back')
    c['elements'][0]['fields'][0].update(helpText='Enter a name',visibilityRule=dict(conditions=[dict(field='showName',operator='EqualTo',value=literal(True))]),validationRule=dict(formulaExpression='LEN({!AccountName}) > 0',errorMessage='Name is required'))
    xml=checked_config(c)
    assert xml.findtext(f'{Q("screens")}/{Q("nextOrFinishButtonLabel")}')=='Save'
    assert xml.findtext(f'{Q("screens")}/{Q("fields")}/{Q("validationRule")}/{Q("errorMessage")}')=='Name is required'


def test_screen_component_inputs_outputs_and_reference():
    c=configs('Screen');c['variables']=[dict(name='selectedAccount',dataType='String',referenceTo='Account')]
    c['elements'][0]['fields'].append(dict(name='AccountLookup',fieldType='ComponentInstance',fieldText='Account',extensionName='flowruntime:lookup',inputParameters=[dict(name='objectApiName',value=literal('Contact')),dict(name='fieldApiName',value=literal('AccountId'))],outputParameters=[dict(name='recordId',variable='selectedAccount')]))
    xml=checked_config(c)
    assert xml.findall(f'{Q("screens")}/{Q("fields")}')[1].findtext(Q('extensionName'))=='flowruntime:lookup'


def test_constants_expressions_templates_xml():
    c=resource_config();c.update(constants=[dict(name='Greeting',dataType='String',value=literal('Hello'))],expressions=[dict(name='CalculatedText',dataType='String',expression='{!Greeting} & " world"')],textTemplates=[dict(name='Message',text='{!Greeting}')])
    c['elements'][0]['assignments'][0]['value']=ref('CalculatedText')
    xml=checked_config(c);assert xml.findtext(f'{Q("constants")}/{Q("name")}')=='Greeting'
    assert xml.findtext(f'{Q("textTemplates")}/{Q("text")}')=='{!Greeting}'


def loop_config():
    c=resource_config();c['variables']=[dict(name='values',dataType='String',isCollection=True,isInput=True),dict(name='current',dataType='String'),dict(name='result',dataType='String',isOutput=True)]
    c['startElement']='Each_Value';c['elements']=[dict(kind='Loop',name='Each_Value',label='Each value',collection='values',currentItem='current',nextValue='Set_Value',next=None),dict(kind='Assignment',name='Set_Value',label='Set result',assignments=[dict(field='result',value=ref('current'))],next='Each_Value')]
    return c


def test_loop_collection_and_feedback_xml():
    xml=checked_config(loop_config());assert xml.findtext(f'{Q("loops")}/{Q("collectionReference")}')=='values'
    assert xml.findtext(f'{Q("loops")}/{Q("nextValueConnector")}/{Q("targetReference")}')=='Set_Value'


@pytest.mark.parametrize('operator',['Add','RemoveAll'])
def test_collection_assignment(operator):
    c=resource_config();c['variables']=[dict(name='values',dataType='String',isCollection=True,isOutput=True)]
    c['elements']=[dict(kind='CollectionAssignment',name='Set_Value',label='Change collection',collection='values',operator=operator,value=literal('Example'),next=None)]
    xml=checked_config(c);assert xml.findtext(f'{Q("assignments")}/{Q("assignmentItems")}/{Q("operator")}')==operator


def test_record_collection_query_loop_bulk_update():
    c=resource_config();c['variables']=[dict(name='records',dataType='SObject',objectType='Account',isCollection=True),dict(name='current',dataType='SObject',objectType='Account'),dict(name='changes',dataType='SObject',objectType='Account',isCollection=True)]
    c['startElement']='Get_Accounts';c['elements']=[
        dict(kind='GetRecords',name='Get_Accounts',label='Get accounts',object='Account',filters=[dict(field='Name',operator='EqualTo',value=literal('Example'))],outputReference='records',getFirstRecordOnly=False,queriedFields=['Id','Name','Description'],next='Each_Account'),
        dict(kind='Loop',name='Each_Account',label='Each account',collection='records',currentItem='current',nextValue='Set_Description',next='Save_Accounts'),
        dict(kind='Assignment',name='Set_Description',label='Set description',assignments=[dict(field='current.Description',value=literal('Updated'))],next='Collect_Changes'),
        dict(kind='CollectionAssignment',name='Collect_Changes',label='Collect changes',collection='changes',operator='Add',value=ref('current'),next='Each_Account'),
        dict(kind='RecordCollection',name='Save_Accounts',label='Save accounts',operation='Update',object='Account',inputReference='changes',next=None)]
    xml=checked_config(c)
    assert xml.findtext(f'{Q("recordLookups")}/{Q("getFirstRecordOnly")}')=='false'
    assert xml.findtext(f'{Q("recordUpdates")}/{Q("inputReference")}')=='changes'


@pytest.mark.parametrize('operation,tag',[('Create','recordCreates'),('Update','recordUpdates'),('Delete','recordDeletes')])
def test_bulk_operation_xml(operation,tag):
    c=resource_config();c['variables']=[dict(name='records',dataType='SObject',objectType='Account',isCollection=True,isInput=True)]
    c['elements']=[dict(kind='RecordCollection',name='Set_Value',label='Bulk operation',operation=operation,object='Account',inputReference='records',next=None)]
    ctx=objects();ctx['Account']['deletable']=True
    assert checked_config(c,ctx).findtext(f'{Q(tag)}/{Q("inputReference")}')=='records'


def test_delete_by_id_is_scoped_and_requires_delete_access():
    c=resource_config();c['variables']=[dict(name='accountId',dataType='String',referenceTo='Account',isInput=True)]
    c['elements']=[dict(kind='DeleteRecordById',name='Set_Value',label='Delete account',object='Account',recordId=ref('accountId'),next=None)]
    ctx=objects()
    with pytest.raises(ValueError,match='deletable'):checked_config(c,ctx)
    ctx['Account']['deletable']=True
    assert checked_config(c,ctx).findtext(f'{Q("recordDeletes")}/{Q("filters")}/{Q("field")}')=='Id'


@pytest.mark.parametrize('action_type',['apex','emailAlert','emailSimple'])
def test_action_xml_contract(action_type):
    c=resource_config();c['elements']=[dict(kind='Action',name='Set_Value',label='Call action',actionType=action_type,actionName='ExampleAction',inputs=[dict(name='input',value=literal('Example'))],outputs=[dict(name='output',variable='result')],next=None)]
    xml=checked_config(c);assert xml.findtext(f'{Q("actionCalls")}/{Q("actionType")}')==action_type
    assert xml.findtext(f'{Q("actionCalls")}/{Q("outputParameters")}/{Q("assignToReference")}')=='result'


def test_subflow_xml_and_self_reference_rejected():
    c=resource_config();c['elements']=[dict(kind='Subflow',name='Set_Value',label='Call subflow',flowName='Existing_Flow',inputs=[dict(name='input',value=literal('Example'))],outputs=[dict(name='output',variable='result')],next=None)]
    assert checked_config(c).findtext(f'{Q("subflows")}/{Q("flowName")}')=='Existing_Flow'
    c['elements'][0]['flowName']='Integrated_Test'
    with pytest.raises(ValueError,match='itself'):checked_config(c)


@pytest.mark.parametrize('async_path',[True,False])
def test_after_save_paths_and_entry_gate(async_path):
    c=resource_config();c.update(contractVersion=2,flowType='RecordTriggered',triggerType='RecordAfterSave',recordTriggerType='CreateAndUpdate',object='Account',doesRequireRecordChangedToMeetCriteria=True,startFilters=[dict(field='Name',operator='EqualTo',value=literal('Example'))])
    c['variables'][0].pop('isOutput');c['elements'].append(dict(kind='Assignment',name='Later',label='Later',assignments=[dict(field='result',value=literal('Later'))],next=None))
    path=dict(name='Later_Path',label='Later path',next='Later')
    path.update(dict(pathType='AsyncAfterCommit') if async_path else dict(timeSource='RecordTriggerEvent',offsetNumber=1,offsetUnit='Days'))
    c['scheduledPaths']=[path]
    xml=checked_config(c)
    assert xml.findtext(f'{Q("start")}/{Q("doesRequireRecordChangedToMeetCriteria")}')=='true'
    assert xml.findtext(f'{Q("start")}/{Q("scheduledPaths")}/{Q("connector")}/{Q("targetReference")}')=='Later'


def test_contract_two_before_save_assigns_triggering_field():
    c=resource_config();c.update(contractVersion=2,flowType='RecordTriggered',triggerType='RecordBeforeSave',recordTriggerType='CreateAndUpdate',object='Account',variables=[])
    c['elements'][0]['assignments'][0]['field']='$Record.Description'
    assert checked_config(c).findtext(f'{Q("start")}/{Q("triggerType")}')=='RecordBeforeSave'


@pytest.mark.parametrize('mode',['Picklist','Records'])
def test_dynamic_choices(mode):
    c=configs('Screen');choice=dict(name='AvailableValues',mode=mode,object='Account')
    ctx=objects()
    if mode=='Picklist':
        choice['picklistField']='Status__c';ctx['Account']['fields'].append(field('Status__c','picklist'))
    else:choice.update(displayField='Name',valueField='Name',filters=[dict(field='Name',operator='EqualTo',value=literal('Example'))])
    c['dynamicChoices']=[choice];c['elements'][0]['fields'][0].update(fieldType='DropdownBox',choiceReferences=['AvailableValues'])
    assert checked_config(c,ctx).findtext(f'{Q("dynamicChoiceSets")}/{Q("name")}')=='AvailableValues'


def test_loop_rejects_dml_and_nonreturning_paths():
    c=loop_config();c['elements'][1]=dict(kind='CreateRecords',name='Set_Value',label='Create account',object='Account',inputAssignments=[dict(field='Name',value=literal('No'))],next='Each_Value')
    with pytest.raises(ValueError,match='Loop bodies'):checked_config(c)
    c=loop_config();c['elements'][1]['next']=None
    with pytest.raises(ValueError,match='return'):checked_config(c)


def test_native_compile_success_and_failure(project,monkeypatch):
    import Backend.AI.app.services.flow_preflight_service as module
    from Backend.AI.app.services.metadata_generator import SalesforceMetadataGenerator
    p=plan('Screen');paths=SalesforceMetadataGenerator(project).generate(p)
    validation=dict(valid=True,deploymentFiles=paths)
    calls=[]
    monkeypatch.setattr(module.shutil,'which',lambda _: 'sf')
    def run(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0,stdout=json.dumps(dict(status=0,result=dict(done=True,success=True,id='VALIDATION'))))
    monkeypatch.setattr(module.subprocess,'run',run)
    assert FlowPreflightService().validate_generated(p,validation,project)['success']
    assert '--dry-run' in calls[0] and calls[0].count('--source-dir')==1
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1,stdout=json.dumps(dict(status=1,result=dict(done=True,success=False,details=dict(componentFailures=[dict(problem='Unknown action')]))))))
    with pytest.raises(ValueError,match='Unknown action'):FlowPreflightService().validate_generated(p,validation,project)


@pytest.mark.parametrize('compile_success',[True,False])
def test_field_list_date_screen_http_pipeline_and_compile_gate(project,monkeypatch,compile_success):
    from Backend.AI.app import main
    from Backend.AI.app.services.plan_store import PlanStore
    from Backend.AI.app.services.metadata_spec_store import MetadataSpecStore
    import Backend.AI.app.services.flow_preflight_service as preflight_module
    c=configs('Screen')
    c['elements'][0].update(nextOrFinishButtonLabel='Save')
    c['elements'][0]['fields']=[dict(name='FieldListName',fieldType='InputField',fieldText='Field List Name',dataType='String',isRequired=True),dict(name='DateOfField',fieldType='InputField',fieldText='Date of Field',dataType='Date',isRequired=True)]
    c['elements'][1].update(object='Field_List__c',inputAssignments=[dict(field='Name',value=ref('FieldListName')),dict(field='Date_of_Field__c',value=ref('DateOfField'))])
    org=dict(name='Field_List__c',label='Field List',createable=True,updateable=True,queryable=True,fields=[field('Id','id'),field('Name',length=80),field('Date_of_Field__c','date')])
    p=plan_data('Screen','DRAFT');p['items'][0]['config']=c
    provider=Mock();provider.generate.return_value=json.dumps(p)
    monkeypatch.chdir(project);monkeypatch.setattr(main,'get_ai_provider',lambda:provider)
    monkeypatch.setattr(main,'plan_store',PlanStore());monkeypatch.setattr(main,'metadata_spec_store',MetadataSpecStore())
    monkeypatch.setattr(FlowPreflightService,'_cli',lambda self,args:[] if args[0]=='org' else org)
    monkeypatch.setattr(preflight_module.shutil,'which',lambda _: 'sf')
    compiled=[]
    def compile_only(command,**kwargs):
        assert '--dry-run' in command
        compiled.append(command)
        return SimpleNamespace(returncode=0 if compile_success else 1,stdout=json.dumps(dict(status=0 if compile_success else 1,result=dict(done=True,success=compile_success))))
    monkeypatch.setattr(preflight_module.subprocess,'run',compile_only)
    deployed=[]
    def deploy(executor,plan,validation_result):
        assert compiled
        xml=ET.parse(executor.project_root/validation_result['deploymentFiles'][0])
        assert xml.findtext(f'{Q("status")}')=='Draft'
        assert xml.findall(f'{Q("screens")}/{Q("fields")}')[1].findtext(Q('dataType'))=='Date'
        deployed.append(True);return {'success':True}
    monkeypatch.setattr(main.SalesforceDeploymentExecutor,'deploy',deploy)
    with TestClient(main.app) as client:
        response=client.post('/api/plan',json=dict(requirement='Create a Screen Flow on Field List with Field List Name and Date of Field and save',salesforce_context=dict(objects=[org])))
        assert response.status_code==200,response.text
        pid=response.json()['id'];assert client.post(f'/api/plans/{pid}/approve').status_code==200
        response=client.post(f'/api/plans/{pid}/generate-metadata');assert response.status_code==200,response.text
        response=client.post(f'/api/plans/{pid}/deploy')
        assert response.status_code==(200 if compile_success else 422),response.text
        assert bool(deployed)==compile_success


def test_capability_endpoint_matches_runtime_contract():
    from Backend.AI.app.main import app
    with TestClient(app) as client:
        result=client.get('/api/flows/capabilities')
        assert result.status_code==200
        data=result.json();assert data['contractVersion']==2
        assert 'Date' in data['screenInputTypes'] and 'Loop' in data['elements']
        assert data['deploymentStatus']=='Draft' and data['activationImplemented'] is False
        assert client.get(data['schemaEndpoint']).json()['$defs']['ScreenField']==flow_config_json_schema()['$defs']['ScreenField']


def test_dependency_catalog_discovery_uses_get_only(monkeypatch):
    from Backend.AI.app.salesforce.metadata_service import SalesforceMetadataService
    service=SalesforceMetadataService('AIOrg');commands=[]
    monkeypatch.setattr(service,'_run_sf_command',lambda command:commands.append(command) or {'result':{'actions':[]}})
    data=service.get_flow_dependency_context('Call an Apex action and existing subflow')
    assert set(data['flowDependencies'])=={'custom/apex','custom/flow'}
    assert all(command[command.index('--method')+1]=='GET' for command in commands)
    assert service.get_flow_dependency_context('Create a Screen Flow to save a record')=={}


def test_provider_exception_is_classified_without_exposing_raw_message():
    provider=Mock();provider.generate.side_effect=OSError('private provider details')
    with pytest.raises(RuntimeError,match='AI provider request failed') as error:
        PlanningService(provider).generate_plan('Create a Screen Flow',salesforce_context={'objects':[]})
    assert 'private provider details' not in str(error.value)


def test_loop_cannot_mutate_iteration_collection():
    c=loop_config();c['elements'][1]=dict(kind='CollectionAssignment',name='Set_Value',label='Remove current',collection='values',operator='RemoveAll',value=ref('current'),next='Each_Value')
    with pytest.raises(ValueError,match='iterating'):checked_config(c)


def test_typed_id_choice_cannot_claim_another_object():
    c=configs('Screen');c['choices']=[dict(name='FakeId',choiceText='Account',dataType='String',value=literal('001fake'))]
    c['elements'][0]['fields'][0].update(fieldType='DropdownBox',choiceReferences=['FakeId'],referenceTo='Account')
    with pytest.raises(ValueError,match='Typed Id choices'):checked_config(c)


def test_provider_output_limit_is_explicit(monkeypatch):
    import Backend.AI.app.providers.ai_provider as module
    client=Mock();client.messages.create.return_value=SimpleNamespace(stop_reason='max_tokens',content=[])
    client.messages.count_tokens.return_value=SimpleNamespace(input_tokens=100)
    monkeypatch.setattr(module.anthropic,'Anthropic',lambda **kwargs:client)
    monkeypatch.setenv('ANTHROPIC_MAX_TOKENS','8192')
    provider=module.AnthropicProvider(api_key='test-key',model='test-model')
    with pytest.raises(RuntimeError,match=r'output(?:-token)? limit'):provider.generate('system','prompt')
    assert client.messages.create.call_args.kwargs['max_tokens']==8192


def test_screen_duplicate_resource_error_identifies_both_locations():
    config = configs('Screen')
    config['variables'] = [{'name': 'AccountName', 'dataType': 'String', 'isInput': True}]
    with pytest.raises(ValueError) as exc:
        validate_flow('Example_Screen', 'Example Screen', config)
    message = str(exc.value)
    assert "Duplicate internal name 'AccountName'" in message
    assert 'elements[0].fields[0].name' in message
    assert 'variables[0].name' in message


def test_screen_bad_internal_name_is_identified():
    config = configs('Screen')
    config['elements'][0]['fields'][0]['name'] = 'Account__Name'
    with pytest.raises(ValueError, match="Invalid internal name 'Account__Name'"):
        validate_flow('Example_Screen', 'Example Screen', config)


def test_screen_direct_reference_needs_no_duplicate_variable():
    config = configs('Screen')
    assert validate_flow('Example_Screen', 'Example Screen', config).variables == []


def test_flow_prompt_explains_screen_resource_namespace():
    from Backend.AI.app.prompts.prompt_builder import build_planning_prompt
    prompt = build_planning_prompt('Create a Screen Flow', context())
    assert 'Do not declare a\nvariable with the same name as a screen input' in prompt
    assert 'never strip their __c suffixes' in prompt


@pytest.mark.parametrize('source_type,declared,expected',[
    ('picklist',None,'Picklist'),('picklist','String','Picklist'),
    ('picklist','Picklist','Picklist'),('multipicklist','Multipicklist','Multipicklist')])
def test_picklist_choice_metadata_type_matches_source(source_type,declared,expected):
    c=configs('Screen');ctx=objects()
    ctx['Account']['fields'].append(field('Categories__c',source_type))
    choice=dict(name='Categories_Choices',mode='Picklist',object='Account',picklistField='Categories__c')
    if declared is not None:choice['dataType']=declared
    c['dynamicChoices']=[choice]
    c['elements'][0]['fields'][0].update(fieldType='DropdownBox',choiceReferences=['Categories_Choices'])
    xml=checked_config(c,ctx)
    assert xml.findtext(f'{Q("dynamicChoiceSets")}/{Q("dataType")}')==expected
    assert xml.findtext(f'{Q("dynamicChoiceSets")}/{Q("picklistField")}')=='Categories__c'
    assert xml.findtext(f'{Q("screens")}/{Q("fields")}/{Q("dataType")}')=='String'


@pytest.mark.parametrize('source_type,declared',[
    ('picklist','Multipicklist'),('multipicklist','Picklist'),('multipicklist','String')])
def test_picklist_choice_wrong_source_type_rejected_before_deployment(source_type,declared):
    c=configs('Screen');ctx=objects()
    ctx['Account']['fields'].append(field('Categories__c',source_type))
    c['dynamicChoices']=[dict(name='Categories_Choices',mode='Picklist',dataType=declared,object='Account',picklistField='Categories__c')]
    c['elements'][0]['fields'][0].update(fieldType='DropdownBox',choiceReferences=['Categories_Choices'])
    with pytest.raises(ValueError,match='requires dataType'):checked_config(c,ctx)


def test_record_choice_xml_stays_string():
    c=configs('Screen')
    c['dynamicChoices']=[dict(name='Account_Choices',mode='Records',object='Account',displayField='Name',valueField='Id',filters=[dict(field='Name',operator='EqualTo',value=literal('Example'))])]
    c['elements'][0]['fields'][0].update(fieldType='DropdownBox',choiceReferences=['Account_Choices'])
    xml=checked_config(c)
    assert xml.findtext(f'{Q("dynamicChoiceSets")}/{Q("dataType")}')=='String'
    assert xml.find(f'{Q("dynamicChoiceSets")}/{Q("picklistField")}') is None
    c['dynamicChoices'][0]['dataType']='Picklist'
    with pytest.raises(ValueError,match='Record choice sets require String'):checked_config(c)


def test_create_task_subject_accepts_described_combobox_text():
    from Backend.AI.app.validators.flow_validator import validate_extended_context, ExtendedFlowConfig
    config = ExtendedFlowConfig.model_validate({
        'flowType':'Autolaunched','status':'Draft','startElement':'Create_Task',
        'elements':[{'kind':'CreateRecords','name':'Create_Task','label':'Create task',
            'object':'Task','inputAssignments':[{'field':'Subject','value':{'type':'String','value':'Follow up'}}],
            'next':None}]})
    metadata = {'Task':{'name':'Task','createable':True,'fields':[
        {'name':'Subject','type':'combobox','createable':True,'length':255}]}}
    validate_extended_context(config, metadata)
