from pathlib import Path

import pytest

from Backend.AI.app.services.metadata_generator import (
    SalesforceMetadataGenerator,
)
from Backend.AI.app.services.metadata_validator import (
    SalesforceMetadataValidator,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


def create_approved_plan():

    return ImplementationPlan.model_validate(
        {
            "id": "PLAN-VALIDATE-001",
            "requirementId": "REQ-VALIDATE-001",
            "summary": "Create Appointment metadata.",
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
                        "Appointment__c."
                        "Appointment_Date__c"
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


def test_validator_requires_approved_plan(
    tmp_path,
):

    validator = SalesforceMetadataValidator(
        project_root=str(tmp_path)
    )

    plan = create_approved_plan()

    plan.status = "DRAFT"

    with pytest.raises(
        ValueError,
        match="Only APPROVED plans can be validated",
    ):
        validator.validate(plan)


def test_validator_detects_missing_metadata(
    tmp_path,
):

    validator = SalesforceMetadataValidator(
        project_root=str(tmp_path)
    )

    plan = create_approved_plan()

    result = validator.validate(
        plan
    )

    assert result["valid"] is False

    assert len(
        result["errors"]
    ) > 0


def test_validator_accepts_generated_metadata(
    tmp_path,
):

    generator = SalesforceMetadataGenerator(
        project_root=str(tmp_path)
    )

    validator = SalesforceMetadataValidator(
        project_root=str(tmp_path)
    )

    plan = create_approved_plan()

    generator.generate(
        plan
    )

    result = validator.validate(
        plan
    )

    assert result["valid"] is True

    assert result["planId"] == (
        "PLAN-VALIDATE-001"
    )

    assert result["status"] == (
        "APPROVED"
    )

    assert len(
        result["validatedFiles"]
    ) == 2

    assert result["errors"] == []


def test_validator_detects_invalid_xml(
    tmp_path,
):

    generator = SalesforceMetadataGenerator(
        project_root=str(tmp_path)
    )

    validator = SalesforceMetadataValidator(
        project_root=str(tmp_path)
    )

    plan = create_approved_plan()

    generator.generate(
        plan
    )

    object_file = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / "Appointment__c"
        / "Appointment__c.object-meta.xml"
    )

    object_file.write_text(
        "<CustomObject>",
        encoding="utf-8",
    )

    result = validator.validate(
        plan
    )

    assert result["valid"] is False

    assert any(
        "Invalid XML"
        in error
        for error in result["errors"]
    )