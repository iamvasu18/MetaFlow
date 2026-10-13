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
    initial=json.loads(p.calls[0]['user_prompt'])
    assert initial['pendingRequirement']=='' and initial['recentMessages']==[]
    assert 'CustomObject' in initial['currentRequestConstraint']
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
