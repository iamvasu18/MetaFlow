import json

import pytest

from Backend.AI.app.services.change_service import (
    ChangeService,
    _parse_change_json,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


# =========================================================
# Fake AI Provider
# =========================================================

class FakeChangeProvider:
    """
    Fake provider used for ChangeService unit tests.

    No real Claude API call is made.
    """

    def __init__(
        self,
        response: str,
    ):
        self.response = response
        self.system_prompt = None
        self.user_prompt = None

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

        return self.response


# =========================================================
# Helpers
# =========================================================

def build_approved_update_plan():
    """
    Build an approved UPDATE implementation plan.
    """

    return ImplementationPlan.model_validate(
        {
            "id": "PLAN-CHANGE-001",
            "requirementId": "REQ-CHANGE-001",
            "summary": (
                "Add Cancelled to the Status picklist."
            ),
            "assumptions": [],
            "items": [
                {
                    "id": "ITEM-001",
                    "action": "UPDATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "AI_Test_Session__c."
                        "Status__c"
                    ),
                    "label": "Status",
                    "dependencies": [
                        "AI_Test_Session__c"
                    ],
                    "config": {
                        "addPicklistValues": [
                            "Cancelled"
                        ]
                    },
                    "approval": "APPROVED",
                }
            ],
            "status": "APPROVED",
        }
    )


def build_salesforce_context():
    """
    Existing Salesforce metadata used as the
    source of truth for the UPDATE.
    """

    return {
        "objects": [
            {
                "name": "AI_Test_Session__c",
                "label": "AI Test Session",
                "fields": [
                    {
                        "name": "Status__c",
                        "fullName": (
                            "AI_Test_Session__c."
                            "Status__c"
                        ),
                        "label": "Status",
                        "type": "Picklist",
                        "required": False,
                        "values": [
                            "Planned",
                            "Active",
                            "Completed",
                        ],
                    }
                ],
            }
        ]
    }


def build_valid_change_response():
    """
    Valid Change v001 AI response.
    """

    return {
        "planId": "PLAN-CHANGE-001",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomField",
                "fullName": (
                    "AI_Test_Session__c."
                    "Status__c"
                ),
                "dependencies": [
                    "AI_Test_Session__c"
                ],
                "changes": {
                    "addPicklistValues": [
                        "Cancelled"
                    ]
                },
            }
        ],
        "validationIssues": [],
    }


# =========================================================
# JSON Parser Tests
# =========================================================

def test_parse_raw_change_json():

    response = json.dumps(
        build_valid_change_response()
    )

    parsed = _parse_change_json(
        response
    )

    assert (
        parsed["planId"]
        == "PLAN-CHANGE-001"
    )

    assert (
        parsed["changes"][0]
        ["metadataType"]
        == "CustomField"
    )


def test_parse_fenced_change_json():

    response = (
        "```json\n"
        + json.dumps(
            build_valid_change_response()
        )
        + "\n```"
    )

    parsed = _parse_change_json(
        response
    )

    assert (
        parsed["planId"]
        == "PLAN-CHANGE-001"
    )


def test_parse_rejects_empty_response():

    with pytest.raises(
        ValueError,
        match="empty response",
    ):

        _parse_change_json(
            ""
        )


def test_parse_rejects_invalid_json():

    with pytest.raises(
        ValueError,
        match="invalid change JSON",
    ):

        _parse_change_json(
            "This is not JSON."
        )


def test_parse_rejects_json_array():

    response = json.dumps(
        [
            {
                "planId": "PLAN-CHANGE-001"
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match="JSON object",
    ):

        _parse_change_json(
            response
        )


def test_parse_rejects_non_string():

    with pytest.raises(
        ValueError,
        match="must be a string",
    ):

        _parse_change_json(
            {
                "invalid": True
            }
        )


# =========================================================
# ChangeService Valid Tests
# =========================================================

def test_generate_valid_change_specification():

    plan = build_approved_update_plan()

    context = build_salesforce_context()

    provider = FakeChangeProvider(
        json.dumps(
            build_valid_change_response()
        )
    )

    service = ChangeService(
        provider=provider
    )

    specification = (
        service.generate_specification(
            plan=plan,
            salesforce_context=context,
        )
    )

    assert (
        specification.planId
        == "PLAN-CHANGE-001"
    )

    assert len(
        specification.changes
    ) == 1

    change = (
        specification.changes[0]
    )

    assert (
        change.itemId
        == "ITEM-001"
    )

    assert (
        change.action
        == "UPDATE"
    )

    assert (
        change.metadataType
        == "CustomField"
    )

    assert (
        change.fullName
        == (
            "AI_Test_Session__c."
            "Status__c"
        )
    )

    assert (
        change.changes[
            "addPicklistValues"
        ]
        == [
            "Cancelled"
        ]
    )


def test_generate_from_fenced_ai_response():

    plan = build_approved_update_plan()

    response = (
        "```json\n"
        + json.dumps(
            build_valid_change_response()
        )
        + "\n```"
    )

    provider = FakeChangeProvider(
        response
    )

    service = ChangeService(
        provider=provider
    )

    specification = (
        service.generate_specification(
            plan=plan,
            salesforce_context=(
                build_salesforce_context()
            ),
        )
    )

    assert (
        specification.planId
        == plan.id
    )


def test_change_prompt_is_sent_to_provider():

    plan = build_approved_update_plan()

    provider = FakeChangeProvider(
        json.dumps(
            build_valid_change_response()
        )
    )

    service = ChangeService(
        provider=provider
    )

    service.generate_specification(
        plan=plan,
        salesforce_context=(
            build_salesforce_context()
        ),
    )

    assert (
        provider.system_prompt
        is not None
    )

    assert (
        provider.user_prompt
        is not None
    )

    assert (
        "change-spec-v001"
        in provider.system_prompt
    )

    assert (
        "PLAN-CHANGE-001"
        in provider.user_prompt
    )

    assert (
        "AI_Test_Session__c.Status__c"
        in provider.user_prompt
    )

    assert (
        "Cancelled"
        in provider.user_prompt
    )


def test_change_prompt_contains_existing_context():

    plan = build_approved_update_plan()

    provider = FakeChangeProvider(
        json.dumps(
            build_valid_change_response()
        )
    )

    service = ChangeService(
        provider=provider
    )

    service.generate_specification(
        plan=plan,
        salesforce_context=(
            build_salesforce_context()
        ),
    )

    assert (
        "Planned"
        in provider.user_prompt
    )

    assert (
        "Active"
        in provider.user_prompt
    )

    assert (
        "Completed"
        in provider.user_prompt
    )


# =========================================================
# Plan Status Tests
# =========================================================

def test_reject_draft_plan():

    plan = build_approved_update_plan()

    plan.status = "DRAFT"

    provider = FakeChangeProvider(
        json.dumps(
            build_valid_change_response()
        )
    )

    service = ChangeService(
        provider=provider
    )

    with pytest.raises(
        ValueError,
        match="Only APPROVED plans",
    ):

        service.generate_specification(
            plan=plan,
            salesforce_context=(
                build_salesforce_context()
            ),
        )


def test_reject_rejected_plan():

    plan = build_approved_update_plan()

    plan.status = "REJECTED"

    provider = FakeChangeProvider(
        json.dumps(
            build_valid_change_response()
        )
    )

    service = ChangeService(
        provider=provider
    )

    with pytest.raises(
        ValueError,
        match="Only APPROVED plans",
    ):

        service.generate_specification(
            plan=plan,
            salesforce_context=(
                build_salesforce_context()
            ),
        )


# =========================================================
# Salesforce Context Tests
# =========================================================

def test_default_salesforce_context():

    plan = build_approved_update_plan()

    provider = FakeChangeProvider(
        json.dumps(
            build_valid_change_response()
        )
    )

    service = ChangeService(
        provider=provider
    )

    specification = (
        service.generate_specification(
            plan=plan,
            salesforce_context=None,
        )
    )

    assert (
        specification.planId
        == plan.id
    )

    assert (
        '"objects": []'
        in provider.user_prompt
    )


def test_reject_invalid_salesforce_context():

    plan = build_approved_update_plan()

    provider = FakeChangeProvider(
        json.dumps(
            build_valid_change_response()
        )
    )

    service = ChangeService(
        provider=provider
    )

    with pytest.raises(
        ValueError,
        match=(
            "Salesforce context must be "
            "a dictionary"
        ),
    ):

        service.generate_specification(
            plan=plan,
            salesforce_context=[],
        )


# =========================================================
# Specification Validation Tests
# =========================================================

def test_reject_wrong_plan_id():

    plan = build_approved_update_plan()

    response = (
        build_valid_change_response()
    )

    response["planId"] = (
        "PLAN-WRONG-999"
    )

    provider = FakeChangeProvider(
        json.dumps(
            response
        )
    )

    service = ChangeService(
        provider=provider
    )

    with pytest.raises(
        ValueError,
        match="planId",
    ):

        service.generate_specification(
            plan=plan,
            salesforce_context=(
                build_salesforce_context()
            ),
        )


def test_reject_invalid_action_from_ai():

    plan = build_approved_update_plan()

    response = (
        build_valid_change_response()
    )

    response["changes"][0][
        "action"
    ] = "DELETE"

    provider = FakeChangeProvider(
        json.dumps(
            response
        )
    )

    service = ChangeService(
        provider=provider
    )

    with pytest.raises(
        ValueError,
        match="invalid change specification",
    ):

        service.generate_specification(
            plan=plan,
            salesforce_context=(
                build_salesforce_context()
            ),
        )


def test_reject_unsupported_field_type_change():

    plan = build_approved_update_plan()

    response = (
        build_valid_change_response()
    )

    response["changes"][0][
        "changes"
    ] = {
        "type": {
            "from": "Picklist",
            "to": "Text",
        }
    }

    provider = FakeChangeProvider(
        json.dumps(
            response
        )
    )

    service = ChangeService(
        provider=provider
    )

    with pytest.raises(
        ValueError,
        match="invalid change specification",
    ):

        service.generate_specification(
            plan=plan,
            salesforce_context=(
                build_salesforce_context()
            ),
        )


def test_reject_duplicate_picklist_values_from_ai():

    plan = build_approved_update_plan()

    response = (
        build_valid_change_response()
    )

    response["changes"][0][
        "changes"
    ][
        "addPicklistValues"
    ] = [
        "Cancelled",
        "Cancelled",
    ]

    provider = FakeChangeProvider(
        json.dumps(
            response
        )
    )

    service = ChangeService(
        provider=provider
    )

    with pytest.raises(
        ValueError,
        match="invalid change specification",
    ):

        service.generate_specification(
            plan=plan,
            salesforce_context=(
                build_salesforce_context()
            ),
        )


def test_accept_validation_issue_response():

    plan = build_approved_update_plan()

    response = {
        "planId": "PLAN-CHANGE-001",
        "changes": [],
        "validationIssues": [
            {
                "code": "METADATA_NOT_FOUND",
                "itemId": "ITEM-001",
                "message": (
                    "Existing Salesforce metadata "
                    "could not be found."
                ),
            }
        ],
    }

    provider = FakeChangeProvider(
        json.dumps(
            response
        )
    )

    service = ChangeService(
        provider=provider
    )

    specification = (
        service.generate_specification(
            plan=plan,
            salesforce_context={
                "objects": []
            },
        )
    )

    assert (
        specification.planId
        == plan.id
    )

    assert (
        specification.changes
        == []
    )

    assert (
        len(
            specification.validationIssues
        )
        == 1
    )

    assert (
        specification
        .validationIssues[0]
        .code
        == "METADATA_NOT_FOUND"
    )


def test_reject_invalid_validation_issue_code():

    plan = build_approved_update_plan()

    response = {
        "planId": "PLAN-CHANGE-001",
        "changes": [],
        "validationIssues": [
            {
                "code": "UNKNOWN_CHANGE_ERROR",
                "itemId": "ITEM-001",
                "message": "Invalid change.",
            }
        ],
    }

    provider = FakeChangeProvider(
        json.dumps(
            response
        )
    )

    service = ChangeService(
        provider=provider
    )

    with pytest.raises(
        ValueError,
        match="invalid change specification",
    ):

        service.generate_specification(
            plan=plan,
            salesforce_context=(
                build_salesforce_context()
            ),
        )