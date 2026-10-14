"""Regression checks for broad Salesforce planning prompt selection."""
from Backend.AI.app.prompts.prompt_builder import build_planning_prompt


def test_lwc_when_clause_does_not_inject_flow_schema():
    prompt = build_planning_prompt(
        "Build an LWC on an App Page that shows Contacts when an Account is selected, with Quick Create.",
        {"objects": []},
    )
    assert "<FLOW_CONFIG_SCHEMA>" not in prompt
    assert "Quick Create" in prompt


def test_explicit_flow_with_lwc_keeps_flow_schema():
    prompt = build_planning_prompt(
        "Create a screen Flow with an embedded LWC for Contact updates.",
        {"objects": []},
    )
    assert "<FLOW_CONFIG_SCHEMA>" in prompt


def test_validation_rules_not_for_unrelated_lwc():
    prompt = build_planning_prompt("Create an LWC search on an App Page", {"objects": []})
    assert "VALIDATION RULE FORMULAS AND DEPENDENCIES" not in prompt


def test_explicit_validation_rule_includes_formula_safety():
    prompt = build_planning_prompt("Create a validation rule with REGEX for Phone", {"objects": []})
    assert "VALIDATION RULE FORMULAS AND DEPENDENCIES" in prompt


def test_implicit_automation_still_includes_flow_contract():
    prompt = build_planning_prompt(
        "When an Opportunity closes, automatically update the related Account",
        {"objects": []},
    )
    assert "<FLOW_CONFIG_SCHEMA>" in prompt
