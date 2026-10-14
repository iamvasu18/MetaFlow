"""Avoid charging code-only planning requests for the integrated Flow contract."""
from Backend.AI.app.prompts.prompt_builder import build_planning_prompt


def test_lwc_planning_omits_long_flow_appendix():
    request = ('Create a Lightning Web Component that searches Contacts related '
               'to an Account, includes a Quick Create Contact form, and can be '
               'added to a Lightning App Page.')
    prompt = build_planning_prompt(request, {'objects': []})
    assert 'TRIGGER PATHS\ncontractVersion 2' not in prompt
    assert '<FLOW_CONFIG_SCHEMA>' not in prompt
    assert '<USER_REQUIREMENT>' in prompt
    assert request in prompt


def test_explicit_flow_retains_integrated_flow_contract():
    prompt = build_planning_prompt('Create a screen Flow to capture Contact details', {'objects': []})
    assert 'TRIGGER PATHS\ncontractVersion 2' in prompt
    assert '<FLOW_CONFIG_SCHEMA>' in prompt


def test_mixed_apex_and_flow_retains_contract():
    prompt = build_planning_prompt('Create an Apex class and a record-triggered Flow', {'objects': []})
    assert 'TRIGGER PATHS\ncontractVersion 2' in prompt
    assert '<FLOW_CONFIG_SCHEMA>' in prompt


def test_lwc_prompt_is_substantially_smaller_than_flow_prompt():
    lwc = build_planning_prompt('Create a Lightning Web Component for Contact search', {'objects': []})
    flow = build_planning_prompt('Create a Flow for Contact search', {'objects': []})
    assert len(lwc) < 0.75 * len(flow)
