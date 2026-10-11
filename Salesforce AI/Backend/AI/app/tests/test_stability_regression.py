from copy import deepcopy
from unittest.mock import Mock
import pytest
from Backend.AI.app.services.planned_context import context_with_planned_components
from Backend.AI.app.services.flow_formula_service import resolve_plan_formulas
from Backend.AI.app.services.custom_object_policy import apply_custom_object_defaults
from Backend.AI.app.services.planning_clarification import planning_error_detail
from Backend.AI.app.validators.plan_validator import ImplementationPlan
from Backend.AI.app.validators.flow_validator import validate_flow_context
from Backend.AI.app.services.flow_preflight_service import FlowPreflightService


def leave_plan():
    items=[{'id':'obj','action':'CREATE','metadataType':'CustomObject','fullName':'Leave_Request__c','label':'Leave Request','config':{'enableReports':True},'approval':'PENDING'}]
    for name,kind in [('Start_Date__c','Date'),('End_Date__c','Date'),('Number_of_Days__c','Number')]:
        items.append({'id':name,'action':'CREATE','metadataType':'CustomField','fullName':'Leave_Request__c.'+name,'label':name,'config':{'fieldType':kind,**({'precision':18,'scale':2} if kind=='Number' else {})},'dependencies':['obj'],'approval':'PENDING'})
    config={'flowType':'RecordTriggered','triggerType':'RecordBeforeSave','recordTriggerType':'CreateAndUpdate','object':'Leave_Request__c','status':'Draft','startElement':'SetDays','elements':[{'kind':'Assignment','name':'SetDays','label':'Set Days','assignments':[{'field':'$Record.Number_of_Days__c','value':{'type':'Reference','value':'InclusiveDays'}}],'next':None}], 'formulas':[{'name':'InclusiveDays','sourceField':'Number_of_Days__c','dataType':'Number','scale':2,'expression':'{!$Record.End_Date__c} - {!$Record.Start_Date__c} + 1'}]}
    items.append({'id':'flow','action':'CREATE','metadataType':'Flow','fullName':'Calculate_Leave_Days','label':'Calculate Leave Days','config':config,'dependencies':['obj','Start_Date__c','End_Date__c','Number_of_Days__c'],'approval':'PENDING'})
    return {'id':'PLAN-leave','requirementId':'leave','summary':'Leave system','status':'DRAFT','items':items}


def resolved():
    plan=leave_plan();context=context_with_planned_components(plan,{'objects':[]})
    return resolve_plan_formulas(plan,context),context


def test_number_stays_number_independent_expression_and_xml():
    data,context=resolved()
    assert data['items'][3]['config']['fieldType']=='Number'
    assert data['items'][4]['config']['formulas']==[]
    assert data['items'][4]['config']['contractVersion']==2
    assert data['items'][4]['config']['expressions'][0]['expression'].endswith('+ 1')
    plan=ImplementationPlan.model_validate(data)
    validate_flow_context(plan,context)


def test_same_plan_preflight_does_not_describe_missing_new_object():
    data,_=resolved();plan=ImplementationPlan.model_validate(data)
    service=FlowPreflightService('real-org')
    service._cli=Mock(return_value=[])
    service.validate(plan)
    assert service._cli.call_count==1


def test_unknown_expression_field_rejected():
    data,context=resolved();data['items'][4]['config']['expressions'][0]['expression']='{!$Record.Missing__c} + 1'
    with pytest.raises(ValueError,match='Unknown or inaccessible'):
        validate_flow_context(ImplementationPlan.model_validate(data),context)


def test_preservation_and_status_rules_not_sharing():
    req='Create leave system. Prevent users from changing Approved unless current status is Submitted. Do not overwrite unrelated metadata. Enable reporting.'
    result=apply_custom_object_defaults(leave_plan(),req)
    assert result['items'][0]['config']['sharingModel']=='Read'
    assert result['items'][0]['config']['enableReports'] is True
    with pytest.raises(ValueError,match='access or sharing'):
        apply_custom_object_defaults(leave_plan(),'Create private leave object with restricted access')


def test_real_org_fields_take_precedence_and_no_mutation():
    data=leave_plan();context={'objects':[{'name':'Leave_Request__c','fields':[{'name':'Number_of_Days__c','type':'string'}]}]}
    before=deepcopy(context);result=context_with_planned_components(data,context)
    assert result['objects'][0]['fields'][0]['type']=='string' and context==before


def test_clarification_specific_and_generic_errors_preserved():
    assert planning_error_detail(ValueError('Formula resource source must be an existing calculated field: Days__c.'))['code']=='CLARIFICATION_REQUIRED'
    assert planning_error_detail(ValueError('Unknown or inaccessible field Foo.Bar'))['question']
    assert planning_error_detail(ValueError('Invalid JSON'))=='Invalid JSON'


def test_independent_expression_generates_real_flow_xml():
    import xml.etree.ElementTree as ET
    from Backend.AI.app.services.flow_generator import flow_xml, Q
    data,_=resolved();item=ImplementationPlan.model_validate(data).items[-1]
    xml=flow_xml(item,'66.0')
    root=ET.fromstring(xml) if isinstance(xml,(str,bytes)) else xml
    formula=root.find(Q('formulas'))
    assert formula.findtext(Q('name'))=='InclusiveDays'
    assert formula.findtext(Q('dataType'))=='Number'
    assert formula.findtext(Q('expression')).endswith('+ 1')
