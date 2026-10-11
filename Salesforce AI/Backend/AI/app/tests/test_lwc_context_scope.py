import json
from copy import deepcopy
from Backend.AI.app.salesforce.context_selector import compact_planning_context
from Backend.AI.app.salesforce.metadata_service import SalesforceMetadataService


def test_controller_does_not_fetch_invocable_catalog(monkeypatch):
    service = SalesforceMetadataService('AIOrg')
    monkeypatch.setattr(service, '_run_sf_command', lambda *a: (_ for _ in ()).throw(AssertionError('Unrelated action discovery')))
    assert service.get_flow_dependency_context('Create an Apex controller for a Contact search LWC') == {}


def test_large_cached_action_catalog_excluded_without_mutating_validation_context():
    context = {'objects': [{'name': 'Contact', 'fields': [{'name': 'Email', 'type': 'email'}]}],
               'flowDependencies': {'custom/apex': {'actions': [{'name': 'Action', 'description': 'x' * 1500000}]}},
               'orgTimeZone': 'UTC'}
    original = deepcopy(context)
    projected = compact_planning_context('Search Contact Email using an Apex controller', context)
    assert len(json.dumps(projected)) < 2000
    assert 'flowDependencies' not in projected
    assert context == original


def test_explicit_flow_action_keeps_contract():
    context = {'objects': [], 'flowDependencies': {'custom/apex': {'actions': [{'name': 'SendAlert'}]}}}
    assert compact_planning_context('Call an Apex action in a Flow', context)['flowDependencies'] == context['flowDependencies']
