import pytest

from Backend.AI.app.services.execution_service import (
    SalesforceExecutionService,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


def create_approved_plan():

    return ImplementationPlan.model_validate(
        {
            "id": "PLAN-EXEC-001",
            "requirementId": "REQ-EXEC-001",
            "summary": "Create Appointment object.",
            "assumptions": [],
            "items": [
                {
                    "id": "ITEM-001",
                    "action": "CREATE",
                    "metadataType": "CustomObject",
                    "fullName": "Appointment__c",
                    "label": "Appointment",
                    "description": (
                        "Stores appointment information."
                    ),
                    "dependencies": [],
                    "approval": "PENDING",
                },
                {
                    "id": "ITEM-002",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "Appointment__c.Appointment_Date__c"
                    ),
                    "label": "Appointment Date",
                    "description": (
                        "Stores appointment date."
                    ),
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "config": {
                        "type": "Date",
                        "required": True,
                    },
                    "approval": "PENDING",
                },
            ],
            "storyPoints": 2,
            "status": "APPROVED",
        }
    )


def test_execution_service_requires_approved_plan():

    service = SalesforceExecutionService()

    plan = create_approved_plan()

    plan.status = "DRAFT"

    with pytest.raises(
        ValueError,
        match="Only APPROVED plans can be executed",
    ):
        service.build_commands(plan)


def test_build_commands_returns_salesforce_commands():

    service = SalesforceExecutionService(
        target_org="AIOrg"
    )

    plan = create_approved_plan()

    commands = service.build_commands(
        plan
    )

    assert len(commands) == 2

    assert commands[0][0] == "sf"
    assert commands[0][1] == "project"
    assert commands[0][2] == "generate"
    assert commands[0][3] == "metadata"

    assert (
        "Appointment__c"
        in commands[0]
    )

    assert (
        "CustomObject"
        in commands[0]
    )


def test_dry_run_does_not_execute_commands():

    service = SalesforceExecutionService(
        target_org="AIOrg"
    )

    plan = create_approved_plan()

    result = service.dry_run(
        plan
    )

    assert result["planId"] == (
        "PLAN-EXEC-001"
    )

    assert result["status"] == (
        "APPROVED"
    )

    assert result["targetOrg"] == (
        "AIOrg"
    )

    assert result["dryRun"] is True

    assert len(
        result["commands"]
    ) == 2