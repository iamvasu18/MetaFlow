from unittest.mock import Mock
from Backend.AI.app.services.conversation_service import ConversationTurn, Intent, respond, concise_clarification
from Backend.AI.app.validators.flow_validator import scalar_type


def test_answered_parent_uses_verified_identity_without_model_questionnaire():
    api = Mock()
    api.list_objects.return_value = [{'name':'Agenda_Item__c','label':'Agenda Item'}]
    api.describe_object.return_value = {'name':'Agenda_Item__c','fields':[]}
    provider = Mock()
    result = respond(ConversationTurn(target_org='AIOrg',message='Agenda Item',
        pending_requirement='Create a field named Test Demo. Use Text(255).',
        pending_question='Which object should I add Test Demo to?'),provider,lambda:api)
    assert result['action']=='build'
    assert result['objects']==['Agenda_Item__c']
    assert 'Test Demo' in result['requirement'] and 'Text(255)' in result['requirement']
    provider.generate.assert_not_called()


def test_ambiguous_parent_does_not_guess_or_generate():
    api = Mock()
    api.list_objects.return_value=[{'name':'One__c','label':'Agenda Item'}, {'name':'Two__c','label':'Agenda Item'}]
    provider = Mock()
    result = respond(ConversationTurn(target_org='AIOrg',message='Agenda Item',pending_requirement='Create Test Demo field.',
        pending_question='Which object should I add Test Demo to?'),provider,lambda:api)
    assert result['action']=='clarify' and 'API name' in result['response']
    api.describe_object.assert_not_called()
    provider.generate.assert_not_called()


def test_explicit_create_update_flow_does_not_reask_trigger_timing():
    intent=Intent(action='clarify',requested_type='Flow',blocking_detail='behavior',
        requirement='When a Case is created or updated with High Priority, assign it to Tier 2.',
        response='Should it also trigger when updated?')
    assert concise_clarification(intent).action=='build'


def test_combobox_text_mapping_and_unknown_type_remains_unknown():
    assert scalar_type({'name':'Subject','type':'combobox'})=='String'
    assert scalar_type({'type':'unverified-type'}) is None
