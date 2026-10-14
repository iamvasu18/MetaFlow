"""Keep published generator contracts aligned with runtime source models."""
import json
from pathlib import Path
import pytest
from Backend.AI.app.validators.metadata_spec_validator import MetadataSpecification
from Backend.AI.app.services.apex_service import ApexSources
from Backend.AI.app.services.lwc_service import LWCSource
from Backend.AI.app.services.planning_service import PlanningService

ROOT = Path(__file__).resolve().parents[4] / 'Prompt Engineering'


def test_initial_plan_contract_cannot_authorize_deployment():
    schema=json.loads((ROOT/'Schemas/plan-v001.json').read_text())
    item=schema['$defs']['planItem']
    assert schema['properties']['status']['const']=='DRAFT'
    assert item['properties']['approval']['const']=='PENDING'
    assert item['properties']['deployment']=={'type':'null'}
    assert {'approval','validation','deployment'} <= set(item['required'])
    assert item['properties']['validation']['required']==['valid','errors','warnings']


@pytest.mark.parametrize('name,model', [('metadata-spec-v001.json',MetadataSpecification),('apex-source-v001.json',ApexSources),('lwc-source-v001.json',LWCSource)])
def test_source_schemas_match_runtime_fields_and_types(name,model):
    published=json.loads((ROOT/'Schemas'/name).read_text())
    runtime=model.model_json_schema()
    assert published['properties']==runtime['properties']
    for key,definition in runtime.get('$defs',{}).items():
        assert published['$defs'][key]['properties']==definition['properties']
        assert published['$defs'][key].get('required')==definition.get('required')


@pytest.mark.parametrize('candidate', [
    {'status':'APPROVED','items':[]},
    {'status':'DRAFT','items':[{'approval':'APPROVED'}]},
    {'status':'DRAFT','items':[{'approval':'PENDING','deployment':{'success':True}}]},
])
def test_backend_rejects_ai_supplied_approval_before_other_processing(candidate):
    with pytest.raises(ValueError,match='AI output'):
        PlanningService._validate_generated_plan(None,candidate,'Create an object',{'objects':[]})


def test_flow_prompts_allow_checked_same_plan_dependencies():
    for name in ['Planning/requirement_to_plan_v002.md','Metadata/plan_to_metadata_v001.md']:
        prompt=(ROOT/name).read_text()
        assert 'New-object/field plus Flow creation in the same plan is not supported' not in prompt
        assert 'same-plan CREATE objects/fields after dependency validation' in prompt


def test_flow_schema_is_generated_from_current_runtime_models():
    from Backend.AI.app.validators.flow_validator import flow_config_json_schema
    published=json.loads((ROOT/'Schemas/flow-config-v001.json').read_text())
    assert published.pop('$schema')=='https://json-schema.org/draft/2020-12/schema'
    assert published == flow_config_json_schema()


def test_explicit_apex_request_does_not_receive_unrelated_flow_schema():
    from Backend.AI.app.prompts.prompt_builder import build_planning_prompt
    prompt=build_planning_prompt('Create an Apex class to retrieve Accounts',{'objects':[]})
    assert '<FLOW_CONFIG_SCHEMA>' not in prompt
    assert '<FLOW_CONFIG_SCHEMA>' in build_planning_prompt('When an Account is created automatically set Rating Hot',{'objects':[]})
