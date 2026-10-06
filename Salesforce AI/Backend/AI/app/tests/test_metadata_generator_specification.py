import pytest

from Backend.AI.app.services.metadata_generator import (
    SalesforceMetadataGenerator,
)
from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
)


def build_metadata_specification():
    return MetadataSpecification.model_validate(
        {
            "planId": "PLAN-001",
            "metadata": [
                {
                    "itemId": "ITEM-001",
                    "action": "CREATE",
                    "metadataType": "CustomObject",
                    "fullName": "AI_Test_Session__c",
                    "label": "AI Test Session",
                    "description": (
                        "Custom object for tracking AI test sessions"
                    ),
                    "dependencies": [],
                    "config": {},
                },
                {
                    "itemId": "ITEM-002",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "AI_Test_Session__c.Session_Date__c"
                    ),
                    "label": "Session Date",
                    "description": None,
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "config": {
                        "type": "Date"
                    },
                },
                {
                    "itemId": "ITEM-003",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "AI_Test_Session__c.Contact_Email__c"
                    ),
                    "label": "Contact Email",
                    "description": None,
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "config": {
                        "type": "Email"
                    },
                },
                {
                    "itemId": "ITEM-004",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "AI_Test_Session__c.Status__c"
                    ),
                    "label": "Status",
                    "description": None,
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "config": {
                        "type": "Picklist",
                        "values": [
                            "Planned",
                            "Active",
                            "Completed",
                        ],
                    },
                },
            ],
            "validationIssues": [],
        }
    )


def test_generate_from_metadata_specification(
    tmp_path,
):
    specification = (
        build_metadata_specification()
    )

    generator = SalesforceMetadataGenerator(
        project_root=str(tmp_path)
    )

    generated_files = (
        generator.generate_from_specification(
            specification
        )
    )

    assert len(generated_files) == 4

    object_file = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / "AI_Test_Session__c"
        / "AI_Test_Session__c.object-meta.xml"
    )

    session_date_file = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / "AI_Test_Session__c"
        / "fields"
        / "Session_Date__c.field-meta.xml"
    )

    contact_email_file = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / "AI_Test_Session__c"
        / "fields"
        / "Contact_Email__c.field-meta.xml"
    )

    status_file = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / "AI_Test_Session__c"
        / "fields"
        / "Status__c.field-meta.xml"
    )

    assert object_file.exists()
    assert session_date_file.exists()
    assert contact_email_file.exists()
    assert status_file.exists()


def test_generated_field_types(
    tmp_path,
):
    specification = (
        build_metadata_specification()
    )

    generator = SalesforceMetadataGenerator(
        project_root=str(tmp_path)
    )

    generator.generate_from_specification(
        specification
    )

    fields_dir = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / "AI_Test_Session__c"
        / "fields"
    )

    session_date_xml = (
        fields_dir
        / "Session_Date__c.field-meta.xml"
    ).read_text(
        encoding="utf-8"
    )

    email_xml = (
        fields_dir
        / "Contact_Email__c.field-meta.xml"
    ).read_text(
        encoding="utf-8"
    )

    status_xml = (
        fields_dir
        / "Status__c.field-meta.xml"
    ).read_text(
        encoding="utf-8"
    )

    assert "<type>Date</type>" in session_date_xml

    assert "<type>Email</type>" in email_xml

    assert "<type>Picklist</type>" in status_xml

    assert "<fullName>Planned</fullName>" in status_xml
    assert "<fullName>Active</fullName>" in status_xml
    assert "<fullName>Completed</fullName>" in status_xml


def test_rejects_specification_with_validation_issues(
    tmp_path,
):
    specification = MetadataSpecification.model_validate(
        {
            "planId": "PLAN-002",
            "metadata": [],
            "validationIssues": [
                {
                    "itemId": "ITEM-001",
                    "code": "UNSUPPORTED_ACTION",
                    "message": (
                        "UPDATE is not supported."
                    ),
                }
            ],
        }
    )

    generator = SalesforceMetadataGenerator(
        project_root=str(tmp_path)
    )

    with pytest.raises(
        ValueError,
        match="validation issues",
    ):
        generator.generate_from_specification(
            specification
        )