import json
from copy import deepcopy
import pytest
from Backend.AI.app.services.component_source_service import repair_sources

PATH = 'force-app/main/default/lwc/example/example.js'

def package():
    return {
        'sourceHash': 'a' * 64, 'requirement': 'Show an example',
        'components': [{'metadataType': 'LightningComponentBundle', 'fullName': 'example'}],
        'files': {PATH: 'original'}, 'baseFiles': {PATH: 'original'},
        'state': 'failed', 'lastResult': {'error': 'Compiler error'},
    }

def test_malformed_reply_retries_without_growing_previous_response():
    original = package()
    before = deepcopy(original)
    class Provider:
        calls = 0
        def generate(self, **kwargs):
            self.calls += 1
            data = json.loads(kwargs['user_prompt'])
            assert data['files'][PATH] == 'original'
            assert 'previousResponse' not in data
            if self.calls == 1:
                return '```json\n{"files":'
            assert 'repairFeedback' in data
            return json.dumps({'files': {PATH: 'corrected'}})
    provider = Provider()
    assert repair_sources(original, 'example', '', provider) == {PATH: 'corrected'}
    assert provider.calls == 2
    assert original == before

def test_repeated_bad_replies_stop_after_three_calls_and_preserve_source():
    original = package()
    before = deepcopy(original)
    class Provider:
        calls = 0
        def generate(self, **kwargs):
            self.calls += 1
            return 'invalid JSON'
    provider = Provider()
    with pytest.raises(ValueError, match='after 3 attempts'):
        repair_sources(original, 'example', '', provider)
    assert provider.calls == 3
    assert original == before

def test_out_of_scope_files_are_never_accepted():
    original = package()
    before = deepcopy(original)
    class Provider:
        calls = 0
        def generate(self, **kwargs):
            self.calls += 1
            return json.dumps({'files': {'force-app/main/default/classes/Other.cls': 'overwrite'}})
    provider = Provider()
    with pytest.raises(ValueError, match='allowed file paths'):
        repair_sources(original, 'example', '', provider)
    assert provider.calls == 3
    assert original == before


def test_flow_repair_can_add_missing_record_resource_without_changing_existing_contract():
    from Backend.AI.app.services.plan_revision_service import RepairProvider
    original={'flowType':'Autolaunched','status':'Draft','startElement':'Get_Queue',
        'variables':[], 'elements':[{'kind':'GetRecords','name':'Get_Queue','object':'Group','next':None}]}
    candidate={'id':'PLAN-ONE','items':[{'id':'ITEM-ONE','action':'CREATE','metadataType':'Flow',
        'fullName':'Escalate','config':original}]}
    config=deepcopy(original)
    config['variables']=[{'name':'QueueRecord','dataType':'SObject','objectType':'Group'}]
    class Provider:
        def generate(self, **kwargs):
            return json.dumps({'repairs':[{'itemId':'ITEM-ONE','config':config}]})
    adapter=RepairProvider(Provider(),{'rejectedPlan':candidate,'originalRequirement':'Find the queue.',
        'failureEvidence':'ITEM-ONE: Unknown Flow resource QueueRecord.Id'})
    result=json.loads(adapter.generate('planning','verified context'))
    assert result['items'][0]['config']['variables'][0]['objectType']=='Group'
    assert candidate['items'][0]['config']['variables']==[]


def test_flow_repair_cannot_delete_or_retype_existing_input():
    from Backend.AI.app.services.plan_revision_service import RepairProvider
    original={'flowType':'Autolaunched','variables':[{'name':'recordId','dataType':'String','isInput':True}],
        'elements':[]}
    candidate={'items':[{'id':'ITEM-ONE','action':'CREATE','metadataType':'Flow','fullName':'Example','config':original}]}
    config=deepcopy(original);config['variables']=[]
    class Provider:
        def generate(self, **kwargs):
            return json.dumps({'repairs':[{'itemId':'ITEM-ONE','config':config}]})
    adapter=RepairProvider(Provider(),{'rejectedPlan':candidate,'originalRequirement':'Keep input.',
        'failureEvidence':'ITEM-ONE error'})
    with pytest.raises(ValueError,match='existing Flow variables'):
        adapter.generate('planning','context')


@pytest.mark.parametrize('mutation',['object','assignment'])
def test_flow_repair_cannot_silently_drop_requested_write(mutation):
    from Backend.AI.app.services.plan_revision_service import RepairProvider
    original={'startElement':'Create_Task','variables':[],'elements':[{'kind':'CreateRecords',
        'name':'Create_Task','object':'Task','inputAssignments':[{'field':'Subject','value':{'type':'String','value':'Follow up'}}]}]}
    candidate={'items':[{'id':'ITEM-ONE','action':'CREATE','metadataType':'Flow','fullName':'Example','config':original}]}
    config=deepcopy(original)
    if mutation=='object':config['elements'][0]['object']='Account'
    else:config['elements'][0]['inputAssignments']=[]
    class Provider:
        def generate(self, **kwargs):
            return json.dumps({'repairs':[{'itemId':'ITEM-ONE','config':config}]})
    adapter=RepairProvider(Provider(),{'rejectedPlan':candidate,'originalRequirement':'Create follow up Task.',
        'failureEvidence':'ITEM-ONE error'})
    with pytest.raises(ValueError,match='Repair cannot'):
        adapter.generate('planning','context')
    assert candidate['items'][0]['config']==original
