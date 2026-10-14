"""Regression checks for requirement-only clarification and bounded metadata reads."""
import json
from Backend.AI.app.services.conversation_service import (
    ConversationTurn, Intent, concise_clarification, read_facts, respond,
)


class Provider:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def generate(self, **kw):
        self.calls.append(kw)
        return json.dumps(self.data)


def test_lookup_requires_target_but_not_optional_question():
    result = concise_clarification(Intent(
        action='build', requested_type='CustomField', create_new=True,
        objects=['Contact'], field='Manager',
        requirement='Create a Lookup field named Manager on Contact',
    ))
    assert result.action == 'clarify'
    assert result.blocking_detail == 'relationship_target' or result.response == 'Which object should this relationship reference?'


def test_lookup_explicit_target_is_buildable():
    result = concise_clarification(Intent(
        action='build', requested_type='CustomField', create_new=True,
        objects=['Contact'], field='Manager',
        requirement='Create a Lookup field named Manager on Contact referencing Account',
    ))
    assert result.action == 'build'


def test_permission_set_missing_grants_as_one_question():
    result = concise_clarification(Intent(
        action='build', requested_type='PermissionSet', create_new=True,
        requirement='Create a Permission Set named Regional Access',
    ))
    assert result.action == 'clarify'
    assert result.response == 'What access should this Permission Set grant?'


def test_explicit_grants_do_not_trigger_permission_question():
    result = concise_clarification(Intent(
        action='build', requested_type='PermissionSet', create_new=True,
        requirement='Create a Permission Set for read access on Account',
    ))
    assert result.action == 'build'


def test_object_existence_check_does_not_describe():
    class Api:
        def list_objects(self):
            return [{'name': 'Account', 'label': 'Account'}]
        def describe_object(self, name):
            raise AssertionError('Unnecessary describe request')
    facts = read_facts(Api(), Intent(action='build', objects=['Account'],
        requested_type='ApexClass', requirement='Create an Apex getter for Accounts'))
    assert facts['objects'][0]['status'] == 'found'


def test_existing_field_does_use_authoritative_describe():
    class Api:
        def list_objects(self):
            return [{'name': 'Account', 'label': 'Account'}]
        def describe_object(self, name):
            assert name == 'Account'
            return {'name': name, 'fields': [{'name':'Phone','label':'Phone','type':'phone'}]}
    facts = read_facts(Api(), Intent(action='build', objects=['Account'], field='Phone',
        requested_type='CustomField', create_new=True, requirement='Create Phone on Account'))
    assert facts['existingRequestedFields'] == ['Account.Phone']


def test_complete_build_one_classifier_call():
    class Api:
        def list_objects(self):
            return [{'name':'Account','label':'Account'}]
        def describe_object(self, name):
            raise AssertionError('No field requested')
    p = Provider({'action':'build','requirement':'Create Apex getter for Account',
        'requested_type':'ApexClass','objects':['Account']})
    r = respond(ConversationTurn(target_org='org', message='Create an Apex getter for Account'),p,lambda:Api())
    assert r['action']=='build'
    assert len(p.calls)==1
