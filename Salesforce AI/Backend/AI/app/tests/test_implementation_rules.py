from Backend.AI.app.prompts.implementation_rules import select_rules


def test_rules_use_declared_components_for_combined_packages():
    rules=select_rules('Create a solution',components=[{'metadataType':'Flow'},{'metadataType':'ApexClass'},{'metadataType':'LightningComponentBundle'}])
    assert all(name+' RULES' in rules for name in ('Flow','Apex','LWC','Integration'))
    assert 'every requested trigger' in rules


def test_simple_apex_does_not_inherit_flow_or_lwc_pack():
    rules=select_rules('Create an Apex class returning Accounts')
    assert 'Apex RULES' in rules
    assert 'Flow RULES' not in rules and 'LWC RULES' not in rules


def test_explicit_flow_and_invocable_apex_include_both_packs():
    rules=select_rules('Create a Flow calling an invocable Apex action')
    assert 'Flow RULES' in rules and 'Apex RULES' in rules and 'Integration RULES' in rules


def test_ordinary_field_request_only_gets_completeness_rules():
    rules=select_rules('Create an Email field on Doctor')
    assert 'REQUIREMENT COMPLETENESS' in rules
    assert 'FLOW DESIGN' not in rules and 'APEX DESIGN' not in rules


def test_lwc_inner_class_contract_is_rejected():
    import pytest
    from Backend.AI.app.services.lwc_apex_contract import controller_contract
    source="public with sharing class Example { public class Payload { @AuraEnabled public String value; } @AuraEnabled public static Payload load() { return new Payload(); } }"
    with pytest.raises(ValueError,match='inner class'):
        controller_contract({'force-app/main/default/classes/Example.cls':source},['Example'])
