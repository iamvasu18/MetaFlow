from pathlib import Path

import pytest

from Backend.AI.app.services.deployment_service import (
    SalesforceDeploymentService,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


def create_test_plan(
    status: str = "DRAFT",
) -> ImplementationPlan:
    """
    Create a deterministic test implementation plan.
    """

    return ImplementationPlan.model_validate(
        {
            "id": "PLAN-DEPLOY-001",
            "requirementId": "REQ-DEPLOY-001",
            "summary": (
                "Create an Appointment custom object."
            ),
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
                    "source": None,
                    "target": None,
                    "config": None,
                    "validation": None,
                    "approval": "APPROVED",
                    "deployment": None,
                }
            ],
            "storyPoints": 1,
            "status": status,
        }
    )


def create_valid_validation_result() -> dict:
    """
    Create a successful metadata validation result.
    """

    return {
        "valid": True,
        "errors": [],
        "validatedFiles": [
            (
                "force-app/main/default/objects/"
                "Appointment__c/"
                "Appointment__c.object-meta.xml"
            )
        ],
    }


def test_deployment_requires_approved_plan():

    service = SalesforceDeploymentService(
        target_org="AIOrg"
    )

    plan = create_test_plan(
        status="DRAFT"
    )

    validation_result = (
        create_valid_validation_result()
    )

    with pytest.raises(
        ValueError,
        match="Only APPROVED plans can be deployed.",
    ):

        service.build_deploy_command(
            plan,
            validation_result,
        )


def test_rejected_plan_cannot_be_deployed():

    service = SalesforceDeploymentService(
        target_org="AIOrg"
    )

    plan = create_test_plan(
        status="REJECTED"
    )

    validation_result = (
        create_valid_validation_result()
    )

    with pytest.raises(
        ValueError,
        match="Only APPROVED plans can be deployed.",
    ):

        service.build_deploy_command(
            plan,
            validation_result,
        )


def test_invalid_metadata_cannot_be_deployed():

    service = SalesforceDeploymentService(
        target_org="AIOrg"
    )

    plan = create_test_plan(
        status="APPROVED"
    )

    validation_result = {
        "valid": False,
        "errors": [
            "Invalid Salesforce metadata."
        ],
        "validatedFiles": [],
    }

    with pytest.raises(
        ValueError,
        match="Metadata validation failed:",
    ):

        service.build_deploy_command(
            plan,
            validation_result,
        )


def test_build_deploy_command():

    service = SalesforceDeploymentService(
        target_org="AIOrg"
    )

    plan = create_test_plan(
        status="APPROVED"
    )

    validation_result = (
        create_valid_validation_result()
    )

    command = service.build_deploy_command(
        plan,
        validation_result,
    )

    expected_source_dir = str(
        Path(
            "force-app",
            "main",
            "default",
            "objects",
            "Appointment__c",
        )
    )

    assert command == [
        "sf",
        "project",
        "deploy",
        "start",
        "--target-org",
        "AIOrg",
        "--source-dir",
        expected_source_dir,
        "--wait",
        "30",
        "--json",
    ]


def test_dry_run_returns_deployment_command():

    service = SalesforceDeploymentService(
        target_org="AIOrg"
    )

    plan = create_test_plan(
        status="APPROVED"
    )

    validation_result = (
        create_valid_validation_result()
    )

    result = service.dry_run(
        plan,
        validation_result,
    )

    expected_source_dir = str(
        Path(
            "force-app",
            "main",
            "default",
            "objects",
            "Appointment__c",
        )
    )

    assert result["planId"] == (
        "PLAN-DEPLOY-001"
    )

    assert result["status"] == (
        "APPROVED"
    )

    assert result["targetOrg"] == (
        "AIOrg"
    )

    assert result["dryRun"] is True

    assert result["command"] == [
        "sf",
        "project",
        "deploy",
        "start",
        "--target-org",
        "AIOrg",
        "--source-dir",
        expected_source_dir,
        "--wait",
        "30",
        "--json",
    ]

    assert result["validatedFiles"] == (
        validation_result["validatedFiles"]
    )