import pytest
from Backend.AI.app.services.conversation_service import Intent, ConversationTurn, respond, concise_clarification

class NoModel:
    def generate(self, **kwargs): raise AssertionError('Unnecessary model call')

@pytest.mark.parametrize('message,label',[('Create a field Render Test','Render Test'),('create an ATM field','ATM')])
def test_named_field_asks_only_parent(message,label):
    result=respond(ConversationTurn(target_org='owned',message=message),NoModel(),lambda:None)
    assert result['response']==f'Which object should I add {label} to?'
    assert 'Text(255)' in result['requirement']

@pytest.mark.parametrize('kind',['CustomObject','ApexClass','LightningComponentBundle','Flow','ValidationRule'])
def test_optional_questions_cannot_block_resolved_supported_request(kind):
    intent=Intent(action='clarify',requested_type=kind,requirement='Create the requested component with supplied behavior',response='What business purpose? Which name? Which settings?')
    assert concise_clarification(intent).action=='build'

@pytest.mark.parametrize('blocker,expected',[('parent_object','Which object should I add Render Test to?'),('behavior','What should it do?'),('relationship_target','Which object should this relationship reference?'),('access','What access should this Permission Set grant?')])
def test_real_blocker_is_one_short_question(blocker,expected):
    result=concise_clarification(Intent(action='clarify',blocking_detail=blocker,field='Render Test',response='Long preamble. Many questions? More questions?'))
    assert result.response==expected
    assert result.response.count('?')==1

def test_supplied_field_name_and_parent_retained_default_type():
    result=concise_clarification(Intent(action='clarify',requested_type='CustomField',field='Render Test',objects=['Bank__c'],requirement='Create Render Test on Bank__c as Text(255)',response='What type?'))
    assert result.action=='build' and result.field=='Render Test' and result.objects==['Bank__c']

def test_permission_grant_is_not_assumed():
    result=concise_clarification(Intent(action='clarify',requested_type='PermissionSet',blocking_detail='access',requirement='Create a permission set',response='Give all settings'))
    assert result.action=='clarify'

def test_genuine_blocker_keeps_a_short_requirement_specific_question():
    result=concise_clarification(Intent(action='clarify',blocking_detail='behavior',requested_type='ApexClass',requirement='Implement the Contact handler',response='Which status should the handler apply?'))
    assert result.response=='Which status should the handler apply?'
    assert result.action=='clarify'
