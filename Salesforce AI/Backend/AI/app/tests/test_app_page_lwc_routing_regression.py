"""Regression checks for the clear App Page request that previously elicited 'What should it do?'"""
import pytest
from Backend.AI.app.services.implementation_routing import (
    requested_lwc_target,
    prefers_explicit_create_lwc,
    resolve_ui_requirement,
    check_ui_plan,
    ImplementationChoiceError,
)

REQUEST = ('Create a Lightning Web Component (LWC) that searches Account-related '
           'Contacts, includes a Quick Create panel, and is placed on an App Page')


def test_explicit_app_page_request_resolves_without_optional_question():
    assert prefers_explicit_create_lwc(REQUEST)
    assert requested_lwc_target(REQUEST) == 'lightning__AppPage'
    rendered = resolve_ui_requirement(REQUEST)
    assert 'lightning__AppPage' in rendered
    assert 'Quick Create' in rendered
    assert 'Account-related' in rendered
    assert resolve_ui_requirement(rendered) == rendered


def test_wrong_target_rejected_and_correct_target_allowed():
    with pytest.raises(ImplementationChoiceError):
        check_ui_plan(REQUEST, {'items': [{'metadataType': 'LightningComponentBundle', 'config': {'targets': ['lightning__HomePage']}}]})
    check_ui_plan(REQUEST, {'items': [{'metadataType': 'LightningComponentBundle', 'config': {'targets': ['lightning__AppPage']}}]})


def test_question_about_app_page_does_not_force_generation():
    question = 'Can an LWC be placed on an App Page?'
    assert not prefers_explicit_create_lwc(question)
    assert resolve_ui_requirement(question) == question
    check_ui_plan(question, {'items': []})


def test_explicit_flow_request_not_replaced_with_lwc():
    instruction = 'Create a Screen Flow for updating Contacts on an App Page'
    assert not prefers_explicit_create_lwc(instruction)
    assert resolve_ui_requirement(instruction) == instruction
