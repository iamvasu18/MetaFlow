import json
from pathlib import Path
from unittest.mock import patch

from Backend.AI.app.services.deployment_executor import (
    SalesforceDeploymentExecutor,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


def create_plan():

    return ImplementationPlan.model_validate(
        {
            "id": "PLAN-EXECUTOR-002",
            "requirementId": "REQ-EXECUTOR-002",
            "summary": "Test deployment.",
            "assumptions": [],
            "items": [
                {
                    "id": "ITEM-001",
                    "action": "CREATE",
                    "metadataType": "CustomObject",
                    "fullName": "TrainingSession__c",
                    "label": "Training Session",
                    "description": (
                        "Stores training session information."
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
            "status": "APPROVED",
        }
    )


def valid_metadata():

    return {
        "valid": True,
        "planId": "PLAN-EXECUTOR-002",
        "status": "APPROVED",
        "validatedFiles": [
            (
                "force-app/main/default/objects/"
                "TrainingSession__c/"
                "TrainingSession__c.object-meta.xml"
            )
        ],
        "errors": [],
    }


@patch(
    "Backend.AI.app.services.deployment_executor.shutil.which"
)
@patch(
    "Backend.AI.app.services.deployment_executor.subprocess.run"
)
def test_successful_deployment(
    mock_run,
    mock_which,
):

    mock_which.return_value = "sf"

    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        json.dumps({"status": 0, "result": {"success": True, "done": True, "checkOnly": False}})
    )
    mock_run.return_value.stderr = ""

    executor = SalesforceDeploymentExecutor(
        target_org="AIOrg"
    )

    result = executor.deploy(
        create_plan(),
        valid_metadata(),
    )

    assert result["success"] is True

    assert result["returnCode"] == 0

    assert result["targetOrg"] == "AIOrg"

    assert result["stdout"] == (
        json.dumps({"status": 0, "result": {"success": True, "done": True, "checkOnly": False}})
    )

    mock_run.assert_called_once()

    command = (
        mock_run.call_args[0][0]
    )

    assert command == [
        "sf",
        "project",
        "deploy",
        "start",
        "--target-org",
        "AIOrg",
        "--source-dir",
        (
            str(executor.project_root / "force-app/main/default/objects/TrainingSession__c")
        ),
        "--wait",
        "30",
        "--json",
    ]


@patch(
    "Backend.AI.app.services.deployment_executor.shutil.which"
)
@patch(
    "Backend.AI.app.services.deployment_executor.subprocess.run"
)
def test_failed_deployment(
    mock_run,
    mock_which,
):

    mock_which.return_value = "sf"

    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""

    mock_run.return_value.stderr = (
        "Deployment failed"
    )

    executor = SalesforceDeploymentExecutor(
        target_org="AIOrg"
    )

    result = executor.deploy(
        create_plan(),
        valid_metadata(),
    )

    assert result["success"] is False

    assert result["returnCode"] == 1

    assert result["stderr"] == (
        "Deployment failed"
    )

    mock_run.assert_called_once()

    command = (
        mock_run.call_args[0][0]
    )

    assert command == [
        "sf",
        "project",
        "deploy",
        "start",
        "--target-org",
        "AIOrg",
        "--source-dir",
        (
            str(executor.project_root / "force-app/main/default/objects/TrainingSession__c")
        ),
        "--wait",
        "30",
        "--json",
    ]


@patch(
    "Backend.AI.app.services.deployment_executor.shutil.which"
)
def test_deployment_requires_salesforce_cli(
    mock_which,
):

    mock_which.return_value = None

    executor = SalesforceDeploymentExecutor(
        target_org="AIOrg"
    )

    plan = create_plan()

    try:

        executor.validate_before_deployment(
            plan,
            valid_metadata(),
        )

        assert False, (
            "Expected Salesforce CLI error"
        )

    except RuntimeError as exc:

        assert (
            "Salesforce CLI 'sf' was not found"
            in str(exc)
        )