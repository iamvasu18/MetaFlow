import os

import pytest
from dotenv import load_dotenv

from Backend.AI.app.providers.ai_provider import (
    AnthropicProvider,
)
from Backend.AI.app.services.metadata_service import (
    MetadataService,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


load_dotenv()


def test_real_claude_metadata_specification():

    # -----------------------------------------------------
    # Skip when Claude credentials are unavailable
    # -----------------------------------------------------

    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip(
            "ANTHROPIC_API_KEY is not configured."
        )

    if not os.getenv("ANTHROPIC_MODEL"):
        pytest.skip(
            "ANTHROPIC_MODEL is not configured."
        )

    # -----------------------------------------------------
    # Approved version of the plan Claude generated
    # -----------------------------------------------------

    plan = ImplementationPlan.model_validate(
        {
            "id": "PLAN-001",
            "requirementId": "REQ-001",
            "summary": (
                "Create custom object AI Test Session "
                "with Session Date, Contact Email, "
                "and Status picklist fields"
            ),
            "assumptions": [],
            "items": [
                {
                    "id": "ITEM-001",
                    "action": "CREATE",
                    "metadataType": "CustomObject",
                    "fullName": "AI_Test_Session__c",
                    "label": "AI Test Session",
                    "description": (
                        "Custom object for tracking "
                        "AI test sessions"
                    ),
                    "dependencies": [],
                    "source": None,
                    "target": {
                        "apiName": "AI_Test_Session__c",
                        "label": "AI Test Session",
                    },
                    "config": {},
                    "validation": None,
                    "approval": "APPROVED",
                    "deployment": None,
                },
                {
                    "id": "ITEM-002",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "AI_Test_Session__c."
                        "Session_Date__c"
                    ),
                    "label": "Session Date",
                    "description": (
                        "Date of the AI test session"
                    ),
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "source": None,
                    "target": {
                        "type": "Date"
                    },
                    "config": {
                        "fieldType": "Date"
                    },
                    "validation": None,
                    "approval": "APPROVED",
                    "deployment": None,
                },
                {
                    "id": "ITEM-003",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "AI_Test_Session__c."
                        "Contact_Email__c"
                    ),
                    "label": "Contact Email",
                    "description": (
                        "Email address associated "
                        "with the test session"
                    ),
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "source": None,
                    "target": {
                        "type": "Email"
                    },
                    "config": {
                        "fieldType": "Email"
                    },
                    "validation": None,
                    "approval": "APPROVED",
                    "deployment": None,
                },
                {
                    "id": "ITEM-004",
                    "action": "CREATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "AI_Test_Session__c."
                        "Status__c"
                    ),
                    "label": "Status",
                    "description": (
                        "Status of the AI test session"
                    ),
                    "dependencies": [
                        "ITEM-001"
                    ],
                    "source": None,
                    "target": {
                        "type": "Picklist",
                        "picklistValues": [
                            "Planned",
                            "Active",
                            "Completed",
                        ],
                    },
                    "config": {
                        "fieldType": "Picklist",
                        "picklistValues": [
                            "Planned",
                            "Active",
                            "Completed",
                        ],
                    },
                    "validation": None,
                    "approval": "APPROVED",
                    "deployment": None,
                },
            ],
            "storyPoints": None,
            "status": "APPROVED",
        }
    )

    # -----------------------------------------------------
    # Real Claude provider
    # -----------------------------------------------------

    provider = AnthropicProvider()

    service = MetadataService(
        provider=provider
    )

    # -----------------------------------------------------
    # Generate real metadata specification
    # -----------------------------------------------------

    specification = (
        service.generate_specification(
            plan=plan,
            salesforce_context={
                "objects": []
            },
        )
    )

    # -----------------------------------------------------
    # Show Claude result
    # -----------------------------------------------------

    print(
        specification.model_dump_json(
            indent=2
        )
    )

    # -----------------------------------------------------
    # Basic assertions
    # -----------------------------------------------------

    assert specification.planId == "PLAN-001"

    assert len(
        specification.metadata
    ) == 4

    metadata_by_name = {
        item.fullName: item
        for item in specification.metadata
    }

    assert (
        metadata_by_name[
            "AI_Test_Session__c.Session_Date__c"
        ].config["type"]
        == "Date"
    )

    assert (
        metadata_by_name[
            "AI_Test_Session__c.Contact_Email__c"
        ].config["type"]
        == "Email"
    )

    status_config = (
        metadata_by_name[
            "AI_Test_Session__c.Status__c"
        ].config
    )

    assert (
        status_config["type"]
        == "Picklist"
    )

    assert status_config["values"] == [
        "Planned",
        "Active",
        "Completed",
    ]