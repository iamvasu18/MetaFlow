import pytest

from Backend.AI.app.services.deployment_executor import (
    SalesforceDeploymentExecutor,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


def create_plan(
    status="APPROVED",
):

    return ImplementationPlan.model_validate(
        {
            "id": "PLAN-EXECUTOR-001",
            "requirementId": "REQ-EXECUTOR-001",
            "summary": "Test deployment.",
            "assumptions": [],
            "items": [],
            "storyPoints": 1,
            "status": status,
        }
    )


def valid_metadata():

    return {
        "valid": True,
        "planId": "PLAN-EXECUTOR-001",
        "status": "APPROVED",
        "validatedFiles": [
            "force-app/main/default/test.xml"
        ],
        "errors": [],
    }


def test_executor_rejects_draft_plan():

    executor = SalesforceDeploymentExecutor(
        target_org="AIOrg"
    )

    plan = create_plan(
        status="DRAFT"
    )

    with pytest.raises(
        ValueError,
        match="Only APPROVED plans can be deployed",
    ):
        executor.validate_before_deployment(
            plan,
            valid_metadata(),
        )


def test_executor_rejects_invalid_metadata():

    executor = SalesforceDeploymentExecutor(
        target_org="AIOrg"
    )

    plan = create_plan()

    invalid_result = {
        "valid": False,
        "errors": [
            "Invalid metadata"
        ],
    }

    with pytest.raises(
        ValueError,
        match="Metadata validation failed",
    ):
        executor.validate_before_deployment(
            plan,
            invalid_result,
        )


def test_executor_requires_target_org():

    executor = SalesforceDeploymentExecutor(
        target_org=""
    )

    plan = create_plan()

    with pytest.raises(
        ValueError,
        match="target org is not configured",
    ):
        executor.validate_before_deployment(
            plan,
            valid_metadata(),
        )