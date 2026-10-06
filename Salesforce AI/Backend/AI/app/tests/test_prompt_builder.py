from Backend.AI.app.prompts.prompt_builder import (
    build_planning_prompt,
    build_metadata_prompt,
    build_change_prompt,
)


# =========================================================
# Planning Prompt Tests
# =========================================================

def test_prompt_contains_requirement():

    requirement = (
        "Create an Appointment custom object."
    )

    salesforce_context = {
        "objects": [
            {
                "name": "Account"
            }
        ]
    }

    prompt = build_planning_prompt(
        requirement=requirement,
        salesforce_context=salesforce_context,
    )

    assert requirement in prompt


def test_prompt_contains_salesforce_context():

    requirement = (
        "Create an Appointment custom object."
    )

    salesforce_context = {
        "objects": [
            {
                "name": "Account"
            }
        ]
    }

    prompt = build_planning_prompt(
        requirement=requirement,
        salesforce_context=salesforce_context,
    )

    assert "Account" in prompt


def test_prompt_does_not_contain_placeholders():

    requirement = (
        "Create an Appointment custom object."
    )

    salesforce_context = {
        "objects": [
            {
                "name": "Account"
            }
        ]
    }

    prompt = build_planning_prompt(
        requirement=requirement,
        salesforce_context=salesforce_context,
    )

    assert "{{requirement}}" not in prompt
    assert "{{salesforce_context}}" not in prompt


# =========================================================
# Metadata Prompt Tests
# =========================================================

def test_metadata_prompt_contains_plan():

    implementation_plan = {
        "id": "PLAN-TEST-001",
        "requirementId": "REQ-001",
        "summary": "Create Training Session object.",
        "assumptions": [],
        "items": [
            {
                "id": "ITEM-001",
                "action": "CREATE",
                "metadataType": "CustomObject",
                "fullName": "TrainingSession__c",
                "label": "Training Session",
                "dependencies": [],
                "config": {},
                "approval": "APPROVED",
            }
        ],
        "status": "APPROVED",
    }

    salesforce_context = {
        "objects": []
    }

    prompt = build_metadata_prompt(
        implementation_plan=implementation_plan,
        salesforce_context=salesforce_context,
    )

    assert "PLAN-TEST-001" in prompt
    assert "TrainingSession__c" in prompt
    assert "ITEM-001" in prompt


def test_metadata_prompt_contains_salesforce_context():

    implementation_plan = {
        "id": "PLAN-TEST-002",
        "requirementId": "REQ-002",
        "summary": "Create a field.",
        "assumptions": [],
        "items": [],
        "status": "APPROVED",
    }

    salesforce_context = {
        "objects": [
            {
                "name": "Contact",
                "label": "Contact",
            }
        ]
    }

    prompt = build_metadata_prompt(
        implementation_plan=implementation_plan,
        salesforce_context=salesforce_context,
    )

    assert "Contact" in prompt


def test_metadata_prompt_does_not_contain_placeholders():

    implementation_plan = {
        "id": "PLAN-TEST-003",
        "requirementId": "REQ-003",
        "summary": "Create metadata.",
        "assumptions": [],
        "items": [],
        "status": "APPROVED",
    }

    salesforce_context = {
        "objects": []
    }

    prompt = build_metadata_prompt(
        implementation_plan=implementation_plan,
        salesforce_context=salesforce_context,
    )

    assert "{{implementation_plan}}" not in prompt
    assert "{{salesforce_context}}" not in prompt


def test_metadata_prompt_rejects_empty_plan():

    implementation_plan = {}

    salesforce_context = {
        "objects": []
    }

    try:

        build_metadata_prompt(
            implementation_plan=implementation_plan,
            salesforce_context=salesforce_context,
        )

        assert False, (
            "Expected ValueError for empty "
            "implementation plan."
        )

    except ValueError as exc:

        assert (
            "Implementation plan cannot be empty."
            in str(exc)
        )


def test_metadata_prompt_rejects_invalid_plan_type():

    implementation_plan = "invalid-plan"

    salesforce_context = {
        "objects": []
    }

    try:

        build_metadata_prompt(
            implementation_plan=implementation_plan,
            salesforce_context=salesforce_context,
        )

        assert False, (
            "Expected ValueError for invalid "
            "implementation plan."
        )

    except ValueError as exc:

        assert (
            "Implementation plan must be a dictionary."
            in str(exc)
        )


def test_metadata_prompt_rejects_invalid_context():

    implementation_plan = {
        "id": "PLAN-TEST-004",
        "requirementId": "REQ-004",
        "summary": "Create metadata.",
        "assumptions": [],
        "items": [],
        "status": "APPROVED",
    }

    salesforce_context = []

    try:

        build_metadata_prompt(
            implementation_plan=implementation_plan,
            salesforce_context=salesforce_context,
        )

        assert False, (
            "Expected ValueError for invalid "
            "Salesforce context."
        )

    except ValueError as exc:

        assert (
            "Salesforce context must be a dictionary."
            in str(exc)
        )


# =========================================================
# Change Prompt Tests
# =========================================================

def test_change_prompt_contains_plan():

    implementation_plan = {
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

    salesforce_context = {
        "objects": []
    }

    prompt = build_change_prompt(
        implementation_plan=implementation_plan,
        salesforce_context=salesforce_context,
    )

    assert "PLAN-CHANGE-001" in prompt

    assert (
        "AI_Test_Session__c.Status__c"
        in prompt
    )

    assert "ITEM-001" in prompt
    assert "Cancelled" in prompt


def test_change_prompt_contains_salesforce_context():

    implementation_plan = {
        "id": "PLAN-CHANGE-002",
        "requirementId": "REQ-CHANGE-002",
        "summary": (
            "Update the Status field."
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
                "config": {},
                "approval": "APPROVED",
            }
        ],
        "status": "APPROVED",
    }

    salesforce_context = {
        "objects": [
            {
                "name": (
                    "AI_Test_Session__c"
                ),
                "label": "AI Test Session",
                "fields": [
                    {
                        "name": "Status__c",
                        "label": "Status",
                        "type": "Picklist",
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

    prompt = build_change_prompt(
        implementation_plan=implementation_plan,
        salesforce_context=salesforce_context,
    )

    assert "AI Test Session" in prompt
    assert "Status__c" in prompt
    assert "Planned" in prompt
    assert "Active" in prompt
    assert "Completed" in prompt


def test_change_prompt_does_not_contain_placeholders():

    implementation_plan = {
        "id": "PLAN-CHANGE-003",
        "requirementId": "REQ-CHANGE-003",
        "summary": (
            "Update existing Salesforce metadata."
        ),
        "assumptions": [],
        "items": [],
        "status": "APPROVED",
    }

    salesforce_context = {
        "objects": []
    }

    prompt = build_change_prompt(
        implementation_plan=implementation_plan,
        salesforce_context=salesforce_context,
    )

    assert (
        "{{IMPLEMENTATION_PLAN}}"
        not in prompt
    )

    assert (
        "{{implementation_plan}}"
        not in prompt
    )

    assert (
        "{{SALESFORCE_CONTEXT}}"
        not in prompt
    )

    assert (
        "{{salesforce_context}}"
        not in prompt
    )


def test_change_prompt_contains_common_rules():

    implementation_plan = {
        "id": "PLAN-CHANGE-004",
        "requirementId": "REQ-CHANGE-004",
        "summary": "Update metadata.",
        "assumptions": [],
        "items": [],
        "status": "APPROVED",
    }

    salesforce_context = {
        "objects": []
    }

    prompt = build_change_prompt(
        implementation_plan=implementation_plan,
        salesforce_context=salesforce_context,
    )

    assert (
        "# COMMON SALESFORCE AI RULES"
        in prompt
    )

    assert (
        "# ACTIVE TASK"
        in prompt
    )


def test_change_prompt_rejects_empty_plan():

    implementation_plan = {}

    salesforce_context = {
        "objects": []
    }

    try:

        build_change_prompt(
            implementation_plan=implementation_plan,
            salesforce_context=salesforce_context,
        )

        assert False, (
            "Expected ValueError for empty "
            "implementation plan."
        )

    except ValueError as exc:

        assert (
            "Implementation plan cannot be empty."
            in str(exc)
        )


def test_change_prompt_rejects_invalid_plan_type():

    implementation_plan = (
        "invalid-change-plan"
    )

    salesforce_context = {
        "objects": []
    }

    try:

        build_change_prompt(
            implementation_plan=implementation_plan,
            salesforce_context=salesforce_context,
        )

        assert False, (
            "Expected ValueError for invalid "
            "implementation plan."
        )

    except ValueError as exc:

        assert (
            "Implementation plan must be a dictionary."
            in str(exc)
        )


def test_change_prompt_rejects_invalid_context():

    implementation_plan = {
        "id": "PLAN-CHANGE-005",
        "requirementId": "REQ-CHANGE-005",
        "summary": "Update metadata.",
        "assumptions": [],
        "items": [],
        "status": "APPROVED",
    }

    salesforce_context = []

    try:

        build_change_prompt(
            implementation_plan=implementation_plan,
            salesforce_context=salesforce_context,
        )

        assert False, (
            "Expected ValueError for invalid "
            "Salesforce context."
        )

    except ValueError as exc:

        assert (
            "Salesforce context must be a dictionary."
            in str(exc)
        )