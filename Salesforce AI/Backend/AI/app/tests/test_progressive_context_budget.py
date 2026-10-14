"""Large-org context regression tests: no lost original metadata or false facts."""
import copy
import json

from Backend.AI.app.salesforce.context_selector import compact_planning_context


def test_oversized_selected_formula_is_explicitly_withheld_not_fabricated():
    original = {'objects': [{'name': 'Account', 'fields': [
        {'name': 'Name', 'type': 'string', 'calculatedFormula': 'X' * 260000},
        {'name': 'Id', 'type': 'id'},
    ]}]}
    before = copy.deepcopy(original)
    result = compact_planning_context('Create an Account search LWC', original)
    field = result['objects'][0]['fields'][0]
    assert field['oversizeDetailsOmitted'] == ['calculatedFormula']
    assert 'calculatedFormula' not in field
    assert len(json.dumps(result)) < 180000
    assert original == before


def test_large_unrelated_field_inventory_does_not_block_lwc_planning():
    fields = [{'name': 'Name', 'type': 'string'}] + [
        {'name': f'Unrelated_{i:05d}__c', 'label': 'Other data', 'type': 'string',
         'description': 'x' * 200} for i in range(15000)
    ]
    data = {'objects': [{'name': 'Contact', 'fields': fields}]}
    result = compact_planning_context('Create an LWC searching Contact Name', data)
    obj = result['objects'][0]
    assert any(f['name'] == 'Name' for f in obj['fields'])
    assert obj['omittedFieldDetailsCount'] == 15000
    assert obj.get('fieldInventoryOmitted') is True
    assert len(json.dumps(result)) < 180000
    assert len(data['objects'][0]['fields']) == 15001


def test_normal_field_details_and_dependencies_are_not_degraded():
    ctx = {'objects': [{'name': 'Account', 'fields': [
        {'name': 'Amount__c', 'calculatedFormula': 'Base__c * 2'},
        {'name': 'Base__c', 'type': 'currency'},
    ]}]}
    result = compact_planning_context('Update Account Amount', ctx)
    assert result['objects'][0]['fields'][0]['calculatedFormula'] == 'Base__c * 2'
    assert any(f['name'] == 'Base__c' for f in result['objects'][0]['fields'])
