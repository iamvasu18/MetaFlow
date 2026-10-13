import json
import pytest
from Backend.AI.app.services.conversation_service import ConversationTurn, respond
class Provider:
    def __init__(self, result): self.result=result; self.calls=[]
    def generate(self, **kw): self.calls.append(kw); return json.dumps(self.result)
def turn(message, **kw): return ConversationTurn(target_org='owned',message=message,**kw)
def test_greeting_never_calls_model_or_org():
    p=Provider({})
    assert respond(turn('Hi'), p, lambda: pytest.fail('No org read'))['action']=='answer'
    assert not p.calls
@pytest.mark.parametrize('action,message,response',[
 ('clarify','Create a field Check','Which object and field type?'),
 ('answer','Can we make email required using Flow?','Yes. Let us discuss the options.')])
def test_non_build_messages_do_not_access_org(action,message,response):
    p=Provider(dict(action=action,response=response,requirement=message,field=''))
    assert respond(turn(message),p,lambda:pytest.fail('No org read'))['action']==action

def test_clarification_preserves_question_for_classifier():
    p=Provider(dict(action='build',response='',requirement='Create Check Text field on Account',field=''))
    result=respond(turn('Account, Text',pending_requirement='Create Check field',pending_question='Which object and type?'),p,lambda:None)
    assert result['requirement']=='Create Check Text field on Account'
    assert json.loads(p.calls[0]['user_prompt'])['pendingQuestion']=='Which object and type?'

def test_search_uses_exact_live_identity_and_describe():
    class Api:
        def list_objects(self):return [{'name':'Meeting__c','label':'Meeting'}]
        def describe_object(self,name):return {'name':name,'fields':[{'name':'Agenda_Item__c','label':'Agenda Item','type':'string'}]}
        def query(self,*a,**kw):pytest.fail('No FieldDefinition query permitted')
    p=Provider(dict(action='find_field',response='',requirement='',field='Agenda Item'))
    result=respond(turn('Where is Agenda Item?'),p,lambda:Api())
    assert result['response'].count('Meeting__c.Agenda_Item__c')==1
    assert 'AnnualRevenue' not in result['response']

def test_search_failure_is_not_reported_as_absence():
    class Api:
        def list_objects(self):return [{'name':'Account'}]
        def describe_object(self,name):raise RuntimeError('Read unavailable')
    p=Provider(dict(action='find_field',response='',requirement='',field='Agenda Item'))
    result=respond(turn('find Agenda Item'),p,lambda:Api())
    assert 'incomplete' in result['response']
    assert 'No matching field' not in result['response']

def test_missing_response_fails_closed_after_bounded_retry():
    p=Provider(dict(action='answer',response='',requirement='',field=''))
    with pytest.raises(ValueError):respond(turn('question'),p,lambda:None)
    assert len(p.calls)==2

def test_implicit_automation_receives_runtime_flow_schema():
    from Backend.AI.app.prompts.prompt_builder import build_planning_prompt
    prompt=build_planning_prompt(
        'When Account Industry is Technology, set Rating to Hot on creation and updates.',
        {'objects': [{'name':'Account','fields':[]}]})
    assert '<FLOW_CONFIG_SCHEMA>' in prompt
    assert 'RecordTriggered' in prompt
    assert 'before-save' in prompt

class SequenceProvider(Provider):
    def generate(self,**kw):
        self.calls.append(kw)
        return json.dumps(self.result[len(self.calls)-1])

class OrgApi:
    def list_objects(self):return [{'name':'Account','label':'Account','labelPlural':'Accounts'}]
    def describe_object(self,name):return {'name':name,'fields':[{'name':'AnnualRevenue','label':'Annual Revenue','type':'currency'}]}

def test_existing_field_is_verified_before_clarifying_and_cannot_build_duplicate():
    p=SequenceProvider([
        dict(action='clarify',response='What type?',field='Annual Revenue',objects=['account'],create_new=True,requested_type='CustomField'),
        dict(action='build',requirement='Create Annual Revenue field on Account')])
    result=respond(turn('create Annual Revenue field on account'),p,lambda:OrgApi())
    assert result['action']=='clarify'
    assert 'Account.AnnualRevenue' in result['response']
    assert 'currency' in p.calls[1]['user_prompt']

def test_missing_object_fact_is_supplied_before_recipient_question():
    p=SequenceProvider([
        dict(action='clarify',response='Who receives email?',objects=['Bank']),
        dict(action='clarify',response='No Bank object was returned. I will include its creation. Which administrator should receive the emails?',requirement='Create Bank and email administrator')])
    result=respond(turn('create Bank and email administrator'),p,lambda:OrgApi())
    assert result['action']=='clarify'
    assert 'not_found_in_accessible_catalog' in p.calls[1]['user_prompt']

def test_unsupported_operation_returns_normal_chat_answer():
    p=Provider(dict(action='unsupported',response='Running arbitrary org services is not available in this workspace yet.'))
    result=respond(turn('run an arbitrary service'),p,lambda:pytest.fail('No org read'))
    assert result['action']=='answer'
    assert 'not available' in result['response']

def test_reuse_reply_is_not_forced_back_into_duplicate_clarification():
    p=SequenceProvider([
        dict(action='answer',response='Reuse',objects=['Account'],field='AnnualRevenue',create_new=False),
        dict(action='answer',response='We can use Account.AnnualRevenue unchanged.')])
    result=respond(turn('reuse the existing AnnualRevenue'),p,lambda:OrgApi())
    assert result['action']=='answer'

def test_read_permission_failure_never_becomes_missing_object():
    from fastapi import HTTPException
    class Api:
        def list_objects(self):raise HTTPException(403,'Read denied')
    p=Provider(dict(action='clarify',response='Details?',objects=['Bank']))
    result=respond(turn('create Bank'),p,lambda:Api())
    assert result['action']=='answer'
    assert 'cannot confirm' in result['response']
    assert 'not found' not in result['response']

def test_ambiguous_object_labels_are_not_selected_arbitrarily():
    from Backend.AI.app.services.conversation_service import read_facts, Intent
    class Api:
        def list_objects(self):return [{'name':'Bank__c','label':'Bank'}, {'name':'OtherBank__c','label':'Bank'}]
        def describe_object(self,name):pytest.fail('Must not select an ambiguous parent')
    facts=read_facts(Api(),Intent(action='clarify',response='Which Bank?',objects=['Bank']))
    assert len(facts['objects'][0]['catalogMatches'])==2

def test_existing_object_create_cannot_become_duplicate_build():
    p=SequenceProvider([
        dict(action='build',requirement='Create object Account',objects=['Account'],create_new=True,requested_type='CustomObject'),
        dict(action='build',requirement='Create Account__c')])
    result=respond(turn('Create object Account'),p,lambda:OrgApi())
    assert result['action']=='clarify'
    assert 'Account' in result['response']

def test_short_field_request_uses_context_aware_classifier():
    p=Provider(dict(action='clarify', response='Which object should contain Check?', requirement='Create a field Check'))
    result=respond(turn('create a field check'),p,lambda:pytest.fail('Unspecified parent'))
    assert result['action']=='clarify'
    assert not p.calls
    assert result['response']=='Which object should I add check to?'


def test_null_optional_facts_are_unknown_not_format_failure():
    p=Provider(dict(action='answer',response='Please describe what you need.',requirement=None,field=None,objects=None,components=None,requested_type=None))
    result=respond(turn('help me understand this'),p,lambda:pytest.fail('No verified object'))
    assert result['action']=='answer'
    assert result['objects']==[]
    assert 'Exact response JSON Schema' in p.calls[0]['system_prompt']

def test_format_retry_receives_specific_validation_error():
    p=SequenceProvider([
        dict(action='build',requirement='',requested_type='Text'),
        dict(action='clarify',response='Which object and field type?',requested_type='CustomField')])
    result=respond(turn('I need a field'),p,lambda:None)
    assert result['action']=='clarify'
    feedback=json.loads(p.calls[1]['user_prompt'])['formatFeedback']
    assert 'requested_type' in feedback['error']

def test_advice_followup_receives_prior_topic_and_does_not_build():
    p=Provider(dict(action='answer',response='For unconditional Email requiredness on Doctor, use field requiredness when supported; use a validation rule for conditional requirements.'))
    result=respond(turn('what is the best practice',recent_messages=[
        {'role':'user','content':'Can we make Email required on Doctor using flows?'},
        {'role':'assistant','content':'We discussed Email requiredness on Doctor__c.'}]),p,lambda:pytest.fail('Advice should not mutate or generate'))
    history=json.loads(p.calls[0]['user_prompt'])['recentMessages']
    assert history[-1]['content'].endswith('Doctor__c.')
    assert result['action']=='answer'
    assert 'Use recentMessages' in p.calls[0]['system_prompt']

def test_permission_request_does_not_confuse_existing_field_or_class_with_new_permission_set():
    class Api:
        def list_objects(self):return [{'name':'Account','label':'Account'}]
        def describe_object(self,name):
            return {'name':name,'fields':[{'name':'PermissionsApiEnabled','type':'boolean'}]} if name=='PermissionSet' else {'name':name,'fields':[{'name':'Phone','label':'Phone','type':'phone'}]}
        def list_components(self,kind):return [{'fullName':'AccountService'}] if kind=='ApexClass' else []
    request='Create Permission Set Account Access for Account Phone read access and AccountService access'
    p=SequenceProvider([
        dict(action='build',requirement=request,field='Phone',objects=['Account'],components=[{'type':'ApexClass','name':'AccountService'}],create_new=True,requested_type='PermissionSet'),
        dict(action='build',requirement=request,create_new=True,requested_type='PermissionSet')])
    result=respond(turn(request),p,lambda:Api())
    assert result['action']=='build'
    assert 'ApiEnabled' in p.calls[1]['user_prompt']
