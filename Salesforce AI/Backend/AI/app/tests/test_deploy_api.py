from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from Backend.AI.app.main import app


# =========================================================
# FastAPI Test Client
# =========================================================

client = TestClient(
    app
)


# =========================================================
# Deploy - Unknown Plan
# =========================================================

def test_deploy_endpoint_requires_existing_plan():

    response = client.post(
        "/api/plans/DOES-NOT-EXIST/deploy"
    )

    assert response.status_code == 404

    assert (
        "Plan not found"
        in response.json()["detail"]
    )


# =========================================================
# Deploy - Plan Must Be Approved
# =========================================================

def test_deploy_endpoint_rejects_unapproved_plan():

    # -----------------------------------------------------
    # Generate plan
    # -----------------------------------------------------

    response = client.post(
        "/api/plan",
        json={
            "requirement": (
                "Create an Appointment custom object."
            )
        },
    )

    assert response.status_code == 200

    plan_id = response.json()["id"]

    # -----------------------------------------------------
    # Do NOT approve
    #
    # Deployment must reject a DRAFT plan.
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/deploy"
    )

    assert response.status_code == 422

    assert (
        "Only APPROVED plans can be deployed"
        in str(
            response.json()["detail"]
        )
    )


# =========================================================
# Deploy - Missing Metadata Specification
# =========================================================

def test_deploy_endpoint_requires_metadata_specification():

    # -----------------------------------------------------
    # Generate plan
    # -----------------------------------------------------

    response = client.post(
        "/api/plan",
        json={
            "requirement": (
                "Create an Appointment custom object."
            )
        },
    )

    assert response.status_code == 200

    plan_id = response.json()["id"]

    # -----------------------------------------------------
    # Approve plan
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/approve"
    )

    assert response.status_code == 200

    # -----------------------------------------------------
    # Do NOT generate metadata.
    #
    # /deploy must now require the exact saved
    # MetadataSpecification.
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/deploy"
    )

    assert response.status_code == 422

    assert (
        "No metadata specification"
        in str(
            response.json()["detail"]
        )
    )


# =========================================================
# Deploy - Success
# =========================================================

@patch(
    "Backend.AI.app.main.metadata_spec_store"
)
@patch(
    "Backend.AI.app.main.SalesforceMetadataGenerator"
)
@patch(
    "Backend.AI.app.main.SalesforceMetadataValidator"
)
@patch(
    "Backend.AI.app.main.SalesforceDeploymentExecutor"
)
def test_deploy_endpoint_success(
    mock_executor_class,
    mock_validator_class,
    mock_generator_class,
    mock_spec_store,
):

    # -----------------------------------------------------
    # Mock Salesforce deployment executor
    # -----------------------------------------------------

    mock_executor = (
        mock_executor_class.return_value
    )

    mock_executor.deploy.return_value = {
        "success": True,
        "planId": "PLAN-MOCK-001",
        "status": "APPROVED",
        "targetOrg": "AIOrg",
        "command": [
            "sf",
            "project",
            "deploy",
            "start",
        ],
        "returnCode": 0,
        "stdout": (
            "Deployment succeeded"
        ),
        "stderr": "",
    }

    # -----------------------------------------------------
    # Generate plan
    # -----------------------------------------------------

    response = client.post(
        "/api/plan",
        json={
            "requirement": (
                "Create an Appointment custom object "
                "with Appointment Date and Status fields."
            )
        },
    )

    assert response.status_code == 200

    plan_id = response.json()["id"]

    # -----------------------------------------------------
    # Approve plan
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/approve"
    )

    assert response.status_code == 200

    # -----------------------------------------------------
    # Mock saved MetadataSpecification
    #
    # This represents the result that would normally have
    # been generated through /generate-metadata.
    # -----------------------------------------------------

    mock_specification = (
        MagicMock()
    )

    mock_specification.planId = (
        plan_id
    )

    mock_specification.validationIssues = []

    mock_specification.model_dump.return_value = {
        "planId": plan_id,
        "metadata": [],
        "validationIssues": [],
    }

    mock_spec_store.get.return_value = (
        mock_specification
    )

    # -----------------------------------------------------
    # Mock metadata XML generation
    # -----------------------------------------------------

    mock_generator = (
        mock_generator_class.return_value
    )

    (
        mock_generator
        .generate_from_specification
        .return_value
    ) = [
        (
            "force-app/main/default/objects/"
            "Appointment__c/"
            "Appointment__c.object-meta.xml"
        ),
        (
            "force-app/main/default/objects/"
            "Appointment__c/fields/"
            "Appointment_Date__c.field-meta.xml"
        ),
        (
            "force-app/main/default/objects/"
            "Appointment__c/fields/"
            "Status__c.field-meta.xml"
        ),
    ]

    # -----------------------------------------------------
    # Mock local metadata validation
    # -----------------------------------------------------

    mock_validator = (
        mock_validator_class.return_value
    )

    mock_validator.validate.return_value = {
        "valid": True,
        "errors": [],
    }

    # -----------------------------------------------------
    # Deploy
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/deploy"
    )

    assert response.status_code == 200

    data = response.json()

    # -----------------------------------------------------
    # Verify API response
    # -----------------------------------------------------

    assert (
        data["message"]
        == "Salesforce deployment completed."
    )

    assert (
        data["planId"]
        == plan_id
    )

    assert (
        data["deployment"]["success"]
        is True
    )

    assert (
        data["deployment"]["returnCode"]
        == 0
    )

    # -----------------------------------------------------
    # Verify saved specification was reused
    # -----------------------------------------------------

    mock_spec_store.get.assert_called_once_with(
        plan_id
    )

    # -----------------------------------------------------
    # Verify XML generation used the exact
    # saved specification.
    # -----------------------------------------------------

    (
        mock_generator
        .generate_from_specification
        .assert_called_once_with(
            mock_specification
        )
    )

    # -----------------------------------------------------
    # Verify metadata validation occurred
    # -----------------------------------------------------

    mock_validator.validate.assert_called_once()

    # -----------------------------------------------------
    # Verify deployment occurred exactly once
    # -----------------------------------------------------

    mock_executor.deploy.assert_called_once()


# =========================================================
# Deploy - Salesforce Deployment Failure
# =========================================================

@patch(
    "Backend.AI.app.main.metadata_spec_store"
)
@patch(
    "Backend.AI.app.main.SalesforceMetadataGenerator"
)
@patch(
    "Backend.AI.app.main.SalesforceMetadataValidator"
)
@patch(
    "Backend.AI.app.main.SalesforceDeploymentExecutor"
)
def test_deploy_endpoint_handles_deployment_failure(
    mock_executor_class,
    mock_validator_class,
    mock_generator_class,
    mock_spec_store,
):

    # -----------------------------------------------------
    # Mock failed Salesforce deployment
    # -----------------------------------------------------

    mock_executor = (
        mock_executor_class.return_value
    )

    mock_executor.deploy.return_value = {
        "success": False,
        "planId": "PLAN-MOCK-001",
        "status": "APPROVED",
        "targetOrg": "AIOrg",
        "command": [
            "sf",
            "project",
            "deploy",
            "start",
        ],
        "returnCode": 1,
        "stdout": "",
        "stderr": (
            "Deployment failed"
        ),
    }

    # -----------------------------------------------------
    # Generate plan
    # -----------------------------------------------------

    response = client.post(
        "/api/plan",
        json={
            "requirement": (
                "Create an Appointment custom object "
                "with Appointment Date and Status fields."
            )
        },
    )

    assert response.status_code == 200

    plan_id = response.json()["id"]

    # -----------------------------------------------------
    # Approve plan
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/approve"
    )

    assert response.status_code == 200

    # -----------------------------------------------------
    # Mock saved MetadataSpecification
    # -----------------------------------------------------

    mock_specification = (
        MagicMock()
    )

    mock_specification.planId = (
        plan_id
    )

    mock_specification.validationIssues = []

    mock_specification.model_dump.return_value = {
        "planId": plan_id,
        "metadata": [],
        "validationIssues": [],
    }

    mock_spec_store.get.return_value = (
        mock_specification
    )

    # -----------------------------------------------------
    # Mock XML generation
    # -----------------------------------------------------

    mock_generator = (
        mock_generator_class.return_value
    )

    (
        mock_generator
        .generate_from_specification
        .return_value
    ) = [
        (
            "force-app/main/default/objects/"
            "Appointment__c/"
            "Appointment__c.object-meta.xml"
        ),
    ]

    # -----------------------------------------------------
    # Mock successful local validation
    # -----------------------------------------------------

    mock_validator = (
        mock_validator_class.return_value
    )

    mock_validator.validate.return_value = {
        "valid": True,
        "errors": [],
    }

    # -----------------------------------------------------
    # Deploy
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/deploy"
    )

    # Salesforce deployment failed, therefore the API
    # must return 502.
    assert response.status_code == 502

    data = response.json()

    assert (
        data["detail"]["success"]
        is False
    )

    assert (
        data["detail"]["returnCode"]
        == 1
    )

    assert (
        data["detail"]["stderr"]
        == "Deployment failed"
    )

    # -----------------------------------------------------
    # Verify specification reuse
    # -----------------------------------------------------

    mock_spec_store.get.assert_called_once_with(
        plan_id
    )

    # -----------------------------------------------------
    # Verify metadata generation
    # -----------------------------------------------------

    (
        mock_generator
        .generate_from_specification
        .assert_called_once_with(
            mock_specification
        )
    )

    # -----------------------------------------------------
    # Verify local validation occurred
    # -----------------------------------------------------

    mock_validator.validate.assert_called_once()

    # -----------------------------------------------------
    # Deployment should still have been attempted once.
    # -----------------------------------------------------

    mock_executor.deploy.assert_called_once()


# =========================================================
# Deploy - Invalid Local Metadata
# =========================================================

@patch(
    "Backend.AI.app.main.metadata_spec_store"
)
@patch(
    "Backend.AI.app.main.SalesforceMetadataGenerator"
)
@patch(
    "Backend.AI.app.main.SalesforceMetadataValidator"
)
@patch(
    "Backend.AI.app.main.SalesforceDeploymentExecutor"
)
def test_deploy_endpoint_rejects_invalid_metadata(
    mock_executor_class,
    mock_validator_class,
    mock_generator_class,
    mock_spec_store,
):

    # -----------------------------------------------------
    # Generate plan
    # -----------------------------------------------------

    response = client.post(
        "/api/plan",
        json={
            "requirement": (
                "Create an Appointment custom object."
            )
        },
    )

    assert response.status_code == 200

    plan_id = response.json()["id"]

    # -----------------------------------------------------
    # Approve plan
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/approve"
    )

    assert response.status_code == 200

    # -----------------------------------------------------
    # Mock saved MetadataSpecification
    # -----------------------------------------------------

    mock_specification = (
        MagicMock()
    )

    mock_specification.planId = (
        plan_id
    )

    mock_specification.validationIssues = []

    mock_specification.model_dump.return_value = {
        "planId": plan_id,
        "metadata": [],
        "validationIssues": [],
    }

    mock_spec_store.get.return_value = (
        mock_specification
    )

    # -----------------------------------------------------
    # Mock generated XML files
    # -----------------------------------------------------

    mock_generator = (
        mock_generator_class.return_value
    )

    (
        mock_generator
        .generate_from_specification
        .return_value
    ) = [
        (
            "force-app/main/default/objects/"
            "Appointment__c/"
            "Appointment__c.object-meta.xml"
        ),
    ]

    # -----------------------------------------------------
    # Local metadata validation fails
    # -----------------------------------------------------

    mock_validator = (
        mock_validator_class.return_value
    )

    mock_validator.validate.return_value = {
        "valid": False,
        "errors": [
            "Invalid Salesforce metadata.",
        ],
    }

    # -----------------------------------------------------
    # Deploy
    # -----------------------------------------------------

    response = client.post(
        f"/api/plans/{plan_id}/deploy"
    )

    assert response.status_code == 422

    data = response.json()

    assert (
        data["detail"]["message"]
        == "Metadata validation failed."
    )

    assert (
        "Invalid Salesforce metadata."
        in data["detail"]["errors"]
    )

    # -----------------------------------------------------
    # Salesforce deployment must never be attempted
    # when local validation fails.
    # -----------------------------------------------------

    mock_executor_class.return_value.deploy.assert_not_called()