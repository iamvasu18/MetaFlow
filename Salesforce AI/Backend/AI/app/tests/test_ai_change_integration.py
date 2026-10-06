import json

from Backend.AI.app.providers.provider_factory import (
    get_ai_provider,
)

from Backend.AI.app.services.change_service import (
    ChangeService,
)

from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


# =========================================================
# Real Claude Change Integration Test
# =========================================================

def test_real_claude_generates_change_specification():

    # -----------------------------------------------------
    # 1. Build an APPROVED UPDATE plan
    # -----------------------------------------------------

    plan = ImplementationPlan.model_validate(
        {
            "id": "PLAN-CHANGE-REAL-001",
            "requirementId": "REQ-CHANGE-REAL-001",
            "summary": (
                "Add Cancelled to the existing "
                "Status picklist."
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

    # -----------------------------------------------------
    # 2. Existing Salesforce context
    #
    # This represents the field that already exists
    # in the Salesforce org.
    # -----------------------------------------------------

    salesforce_context = {
        "objects": [
            {
                "name": "AI_Test_Session__c",
                "fullName": "AI_Test_Session__c",
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

    # -----------------------------------------------------
    # 3. Get REAL configured AI provider
    # -----------------------------------------------------

    provider = get_ai_provider()

    # -----------------------------------------------------
    # 4. Create ChangeService
    # -----------------------------------------------------

    service = ChangeService(
        provider=provider
    )

    # -----------------------------------------------------
    # 5. Call REAL Claude
    # -----------------------------------------------------

    specification = (
        service.generate_specification(
            plan=plan,
            salesforce_context=(
                salesforce_context
            ),
        )
    )

    # -----------------------------------------------------
    # 6. Print result for inspection
    # -----------------------------------------------------

    print(
        "\nREAL CLAUDE CHANGE SPECIFICATION:\n"
    )

    print(
        json.dumps(
            specification.model_dump(),
            indent=2,
        )
    )

    # -----------------------------------------------------
    # 7. Validate high-level result
    # -----------------------------------------------------

    assert (
        specification.planId
        == "PLAN-CHANGE-REAL-001"
    )

    assert (
        specification.validationIssues
        == []
    )

    assert len(
        specification.changes
    ) == 1

    # -----------------------------------------------------
    # 8. Validate generated UPDATE
    # -----------------------------------------------------

    change = specification.changes[0]

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

    # -----------------------------------------------------
    # 9. Verify only Cancelled is added
    # -----------------------------------------------------

    assert (
        change.changes[
            "addPicklistValues"
        ]
        == [
            "Cancelled"
        ]
    )

    # -----------------------------------------------------
    # 10. Safety checks
    # -----------------------------------------------------

    assert (
        "type"
        not in change.changes
    )

    assert (
        "removePicklistValues"
        not in change.changes
    )

    assert (
        "delete"
        not in change.changes
    )