import json
import pytest
from Backend.AI.app.services.conversation_service import ConversationTurn, respond
from Backend.AI.app.salesforce.context_selector import compact_planning_context
from Backend.AI.app.services.planning_service import _parse_ai_json, AIResponseFormatError
from Backend.AI.app.services.metadata_service import PlanningProvider

class Provider:
    def __init__(self, result): self.result=result; self.calls=[]
    def generate(self, **kwargs): self.calls.append(kwargs); return json.dumps(self.result)

class Api:
    def list_objects(self): return []

def test_explicit_object_discards_prior_lwc_context_and_checks_current_identity():
    p=Provider({'action':'build','requirement':'Create object Hosted; assume a basic standalone custom object.', 'requested_type':'CustomObject','create_new':True,'objects':['Hosted']})
    result=respond(ConversationTurn(target_org='owned',message='Create object Hosted',pending_requirement='Create an LWC',pending_question='What LWC fields?'),p,lambda:Api())
    assert result['action']=='build'
    assert not p.calls
    assert 'LWC' not in result['requirement']
    assert result['requested_type']=='CustomObject'

def test_context_omits_catalogs_and_unrelated_relationship_payload_without_mutation():
    metadata={'objectCatalog':[{'name':'Unrelated','source':'x'*400000}], 'existingComponents':{'ApexClass':['x'*400000]},'objects':[{'name':'Opportunity','fields':[{'name':'Name','type':'string'}],'relationships':[{'relationshipName':'Items','childSObject':'OpportunityLineItem','irrelevant':'x'*400000}]}]}
    projected=compact_planning_context('Search Opportunity',metadata)
    assert len(json.dumps(projected))<3000
    assert 'objectCatalog' not in projected
    assert 'irrelevant' in metadata['objects'][0]['relationships'][0]

def test_supplemental_inventory_is_not_appended_to_selected_prompt():
    p=Provider({})
    PlanningProvider(p,{'existingComponents':{'ApexClass':['x'*400000]}}).generate('system','selected')
    assert len(p.calls[0]['user_prompt'])<3000

def test_genuinely_large_relevant_context_stops_before_generation():
    with pytest.raises(ValueError,match='still too large'):
        compact_planning_context('Account',{'objects':[{'name':'Account','fields':[{'name':'Name','type':'string','extra':'x'*250000}]}]})

@pytest.mark.parametrize('value',['```json\n{"ok":true}\n```','```json\n{"ok":true}```','{"ok":true}'])
def test_complete_json_formats(value): assert _parse_ai_json(value)=={'ok':True}

@pytest.mark.parametrize('value',['```json\n{"ok":true}', '```json\n{"ok":true}``` extra','{"ok":true}{"second":true}'])
def test_invalid_json_is_never_silently_extracted(value):
    with pytest.raises(AIResponseFormatError): _parse_ai_json(value)

@pytest.mark.parametrize('message',['Create a Samsung object','Create an Samsung object','Create an object named Samsung','Create object Samsung','Create a Samsung custom object'])
def test_basic_object_word_orders_use_defaults_without_model(message):
    p=Provider({})
    result=respond(ConversationTurn(target_org='owned',message=message),p,lambda:Api())
    assert result['action']=='build'
    assert result['objects']==['Samsung']
    assert 'no additional custom fields' in result['requirement']
    assert not p.calls

def test_just_create_reply_resolves_previous_object_without_optional_question():
    result=respond(ConversationTurn(target_org='owned',message='Just Create Object',pending_requirement='Create an Samsung object',pending_question='What business purpose?'),Provider({}),lambda:Api())
    assert result['action']=='build' and result['objects']==['Samsung']


def test_optional_lwc_question_becomes_build_without_extra_confirmation():
    from Backend.AI.app.services.conversation_service import Intent, apply_optional_defaults
    result=apply_optional_defaults(Intent(action='clarify',response='Which fields should display in search results?',requested_type='LightningComponentBundle',requirement='Create an LWC to search Opportunity'), 'Create an LWC to search Opportunity')
    assert result.action=='build' and 'assumptions' in result.requirement

def test_actual_identity_conflict_is_not_suppressed():
    from Backend.AI.app.services.conversation_service import Intent, apply_optional_defaults
    result=apply_optional_defaults(Intent(action='clarify',response='Business purpose?',requested_type='CustomObject'), 'Create a Samsung object', facts={'existingRequestedObjects':['Samsung__c']})
    assert result.action=='clarify'

def test_question_and_missing_field_parent_are_not_forced_into_build():
    from Backend.AI.app.services.conversation_service import Intent, apply_optional_defaults
    intent=Intent(action='clarify',response='Which object and what field type?',requested_type='CustomField',field='Check')
    assert apply_optional_defaults(intent,'Create a field Check').action=='clarify'
    assert apply_optional_defaults(Intent(action='clarify',response='Business purpose?',requested_type='CustomObject'),'Can we create an object?').action=='clarify'
