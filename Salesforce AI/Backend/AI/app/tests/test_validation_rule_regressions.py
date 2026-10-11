from types import SimpleNamespace as NS
from unittest.mock import Mock
from copy import deepcopy
import xml.etree.ElementTree as ET
import pytest
from Backend.AI.app.validators.metadata_spec_validator import validate_formula_regex_escaping, MetadataSpecification
from Backend.AI.app.services.metadata_service import load_metadata_generation_context
from Backend.AI.app.services.metadata_generator import SalesforceMetadataGenerator
from Backend.AI.app.validators.plan_validator import ImplementationPlan, validate_plan

BAD = r'AND(NOT(ISBLANK(Phone_Number__c)), NOT(REGEX(Phone_Number__c, "^\+91[0-9]{10}$")))'
GOOD = BAD.replace(r'\+', '[+]')


def item(formula=GOOD):
    return dict(id='ITEM-001', action='CREATE', metadataType='ValidationRule',
                fullName='Field_List__c.Phone_Number_Format', label='Phone Number Format',
                dependencies=[], approval='APPROVED', config=dict(active=True,
                errorConditionFormula=formula, errorMessage='Use +91 and ten digits.',
                errorDisplayField='Phone_Number__c'))


def plan(formula=GOOD):
    return ImplementationPlan.model_validate(dict(id='PLAN-REGEX',requirementId='REQ-REGEX',
        summary='Validate phone', status='APPROVED', items=[item(formula)]))


def spec(formula=GOOD):
    data=item(formula);data['itemId']=data.pop('id');data.pop('approval')
    return MetadataSpecification.model_validate(dict(planId='PLAN-REGEX', metadata=[data]))


def test_invalid_escape_rejected_during_planning():
    result=validate_plan(plan(BAD).model_dump())
    assert not result.valid
    assert any('single-backslash-plus' in error for error in result.errors)


def test_invalid_escape_rejected_in_metadata_spec():
    with pytest.raises(ValueError, match='single-backslash-plus'):
        spec(BAD)


@pytest.mark.parametrize('formula', [GOOD, BAD.replace('\\', '\\\\')])
def test_valid_formula_survives_xml_serialization_exactly(tmp_path, formula):
    paths=SalesforceMetadataGenerator(tmp_path).generate_from_specification(spec(formula))
    text=ET.parse(paths[0]).getroot().find('{http://soap.sforce.com/2006/04/metadata}errorConditionFormula').text
    assert text == formula


def test_direct_generator_also_rejects_invalid_escape(tmp_path):
    with pytest.raises(ValueError, match='single-backslash-plus'):
        SalesforceMetadataGenerator(tmp_path).generate(plan(BAD))


def test_existing_target_context_loaded_from_plan():
    service=Mock();service.get_context.return_value={'objects':[{'name':'Field_List__c','fields':[{'name':'Phone_Number__c'}]}]}
    context=load_metadata_generation_context(plan(),service)
    service.get_context.assert_called_once_with(['Field_List__c'])
    assert context['objects'][0]['fields'][0]['name']=='Phone_Number__c'


def test_planned_objects_are_not_described_as_existing():
    new=NS(id='OBJ',action='CREATE',metadataType='CustomObject',fullName='Employee__c',config={},dependencies=[])
    field=NS(id='FIELD',action='CREATE',metadataType='CustomField',fullName='Employee__c.Vendor__c',config={'referenceTo':'Account'},dependencies=['OBJ'])
    rule=NS(id='RULE',action='CREATE',metadataType='ValidationRule',fullName='Employee__c.Check_Vendor',config={},dependencies=['FIELD'])
    service=Mock();service.get_context.return_value={'objects':[{'name':'Account','fields':[]}]}
    result=load_metadata_generation_context(NS(items=[new,field,rule]),service)
    service.get_context.assert_called_once_with(['Account'])
    assert [x['fullName'] for x in result['plannedComponents']]==['Employee__c','Employee__c.Vendor__c']


def test_generate_metadata_endpoint_passes_discovered_context(monkeypatch):
    import Backend.AI.app.main as main
    approved=plan(); expected={'objects':[{'name':'Field_List__c','fields':[{'name':'Phone_Number__c'}]}]}
    monkeypatch.setattr(main.plan_store,'get',lambda _:approved)
    org=Mock();org.get_context.return_value=deepcopy(expected)
    monkeypatch.setattr(main,'SalesforceMetadataService',lambda **kw:org)
    monkeypatch.setattr(main,'get_ai_provider',lambda:Mock())
    converter=Mock();converter.generate_specification.return_value=spec()
    monkeypatch.setattr(main,'MetadataService',lambda **kw:converter)
    generator=Mock();generator.generate_from_specification.return_value=[]
    monkeypatch.setattr(main,'SalesforceMetadataGenerator',lambda **kw:generator)
    monkeypatch.setattr(main.metadata_spec_store,'save',lambda _:None)
    main.generate_metadata(approved.id)
    actual=converter.generate_specification.call_args.kwargs['salesforce_context']
    assert actual['objects']==expected['objects']


def test_flow_only_deterministic_conversion_needs_no_extra_discovery():
    service=Mock()
    result=load_metadata_generation_context(NS(items=[NS(metadataType='Flow',action='CREATE')]),service)
    assert result == {'objects': []}
    service.get_context.assert_not_called()
