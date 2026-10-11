from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import json
import pytest
from Backend.AI.app.salesforce.context_selector import SalesforceContextSelector, compact_planning_context
from Backend.AI.app.providers.ai_provider import AnthropicProvider


def test_explicit_object_beats_incidental_name_fields():
    data = {'objects': [
        {'name': 'Account', 'label': 'Account', 'fields': [{'name': 'Name'}]},
        {'name': 'Field_List__c', 'label': 'Field List', 'fields': [{'name': 'Name'}]},
    ]}
    assert [x['name'] for x in SalesforceContextSelector().select(
        'Create a Screen Flow on Field List with Name input', data)['objects']][0] == 'Field_List__c'


def test_projection_retains_inventory_required_fields_formula_dependencies_and_original():
    data = {'objects': [{'name': 'Example__c', 'fields': [
        {'name': 'Days__c', 'label': 'Days', 'calculatedFormula': 'TODAY() - Start__c'},
        {'name': 'Start__c', 'type': 'date', 'precision': 12},
        {'name': 'Mandatory__c', 'required': True, 'values': ['Allowed']},
        {'name': 'Unused__c', 'type': 'picklist', 'picklistValues': ['x'*100]*1000},
    ]}], 'orgTimeZone': 'UTC'}
    original = deepcopy(data)
    result = compact_planning_context('Check Days', data)
    fields = result['objects'][0]['fields']
    assert fields[:3] == data['objects'][0]['fields'][:3]
    assert fields[3]['name'] == 'Unused__c' and fields[3]['detailsOmitted']
    assert len(json.dumps(result)) < len(json.dumps(data)) / 20
    assert data == original
    assert result['orgTimeZone'] == 'UTC'


def provider(monkeypatch, count):
    monkeypatch.setenv('ANTHROPIC_MAX_INPUT_TOKENS', '180000')
    monkeypatch.setenv('ANTHROPIC_MAX_TOKENS', '4096')
    with patch('Backend.AI.app.providers.ai_provider.anthropic.Anthropic') as factory:
        client = factory.return_value
        client.messages.count_tokens.return_value = SimpleNamespace(input_tokens=count)
        client.messages.create.return_value = SimpleNamespace(
            stop_reason='end_turn', content=[SimpleNamespace(type='text', text='{}')])
        return AnthropicProvider(api_key='fake', model='test'), client


def test_oversize_never_calls_generation(monkeypatch):
    service, client = provider(monkeypatch, 250490)
    with pytest.raises(ValueError, match='250490 tokens'):
        service.generate('system', 'user')
    client.messages.create.assert_not_called()


def test_count_and_generation_use_identical_content(monkeypatch):
    service, client = provider(monkeypatch, 100)
    assert service.generate('system', 'user') == '{}'
    counted = client.messages.count_tokens.call_args.kwargs
    generated = client.messages.create.call_args.kwargs
    for key in ('model', 'system', 'messages'):
        assert counted[key] == generated[key]
