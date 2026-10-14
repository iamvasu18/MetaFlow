"""Non-network regression checks for planned Apex completeness and bounded repairs."""
from pathlib import Path
import pytest
from Backend.AI.app.services.apex_service import ApexRequest, ApexSources, ApexAutomationService, SYSTEM_PROMPT


def test_generation_request_carries_all_planned_names():
    r = ApexRequest(class_name='AccountController', requirement='Build an LWC controller', expected_components=[
        ('ApexClass', 'AccountController'), ('ApexClass', 'AccountControllerTest')])
    assert r.expected_components == [('ApexClass', 'AccountController'), ('ApexClass', 'AccountControllerTest')]


def test_generation_prompt_explicitly_enforces_security_and_soql_order():
    assert 'insert as user' in SYSTEM_PROMPT
    assert 'before WHERE' in SYSTEM_PROMPT
    assert 'Every planned component' in SYSTEM_PROMPT


def test_metadata_path_propagates_required_inventory():
    source = (Path(__file__).parents[1] / 'services' / 'metadata_service.py').read_text(encoding='utf-8')
    assert 'expected_components=[(item.metadataType, item.fullName) for item in apex]' in source


def test_retry_avoids_resending_large_previous_source():
    source = (Path(__file__).parents[1] / 'services' / 'apex_service.py').read_text(encoding='utf-8')
    assert 'response[:650000]' not in source
    assert 'Apex generator omitted planned components:' in source
