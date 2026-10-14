from copy import deepcopy
import pytest
from Backend.AI.app.services.permission_set_service import PermissionSetConfig
from Backend.AI.app.services.permission_set_plan_policy import sanitize_planned_permission_sets


def test_alias_with_valid_grants():
    config = PermissionSetConfig.model_validate({'objectPermissions': [
        {'object': 'Account', 'allowRead': True, 'allowUpdate': True}]})
    assert config.objectPermissions[0].allowEdit is True
    assert 'allowUpdate' not in config.model_dump_json()


def test_false_alias_remains_false():
    config = PermissionSetConfig.model_validate({'objectPermissions': [
        {'object': 'Account', 'allowUpdate': False}]})
    assert config.objectPermissions[0].allowEdit is False


def test_equal_aliases_accepted():
    config = PermissionSetConfig.model_validate({'objectPermissions': [
        {'object': 'Account', 'allowRead': True, 'allowEdit': True, 'allowUpdate': True}]})
    assert config.objectPermissions[0].allowEdit is True


@pytest.mark.parametrize('edit,update', [(True, False), (False, True)])
def test_conflicting_alias_rejected(edit, update):
    with pytest.raises(ValueError, match='Conflicting'):
        PermissionSetConfig.model_validate({'objectPermissions': [
            {'object': 'Account', 'allowRead': True, 'allowEdit': edit, 'allowUpdate': update}]})


@pytest.mark.parametrize('bad', ['true', 1, None, [], {}])
def test_alias_does_not_relax_strict_boolean(bad):
    with pytest.raises(ValueError):
        PermissionSetConfig.model_validate({'objectPermissions': [
            {'object': 'Account', 'allowRead': True, 'allowUpdate': bad}]})


def test_unknown_grant_still_rejected():
    with pytest.raises(ValueError):
        PermissionSetConfig.model_validate({'objectPermissions': [
            {'object': 'Account', 'allowRead': True, 'administrator': True}]})


@pytest.fixture
def plan():
    return {'items': [
        {'id': 'controller', 'metadataType': 'ApexClass', 'action': 'CREATE', 'dependencies': []},
        {'id': 'permission', 'metadataType': 'PermissionSet', 'action': 'CREATE', 'dependencies': []},
        {'id': 'lwc', 'metadataType': 'LightningComponentBundle', 'action': 'CREATE', 'dependencies': ['controller']},
    ]}


def test_remove_unrequested_grants(plan):
    original = deepcopy(plan)
    result = sanitize_planned_permission_sets(plan, 'Create an LWC that searches Contacts related to an Account')
    assert [item['id'] for item in result['items']] == ['controller', 'lwc']
    assert plan == original


def test_explicit_grants_preserved(plan):
    assert sanitize_planned_permission_sets(plan, 'Create an LWC and grant Contact read access') == plan
    assert sanitize_planned_permission_sets(plan, 'Create a Permission Set for Contact') == plan


def test_dependent_item_must_not_be_silently_broken(plan):
    plan['items'][2]['dependencies'].append('permission')
    with pytest.raises(ValueError, match='depends on an unrequested'):
        sanitize_planned_permission_sets(plan, 'Create a Contact search LWC')


def test_only_unrequested_grants_does_not_create_empty_plan():
    with pytest.raises(ValueError, match='no implementation remains'):
        sanitize_planned_permission_sets({'items':[{'id':'p', 'metadataType':'PermissionSet', 'action':'CREATE'}]}, 'Create LWC')
