from Backend.AI.app.validators.plan_validator import validate_plan


def test_valid_plan():

    plan = {
        "id": "PLAN-001",
        "requirementId": "REQ-001",
        "summary": "Create an Appointment object",
        "assumptions": [],
        "status": "DRAFT",
        "items": [
            {
                "id": "ITEM-001",
                "action": "CREATE",
                "metadataType": "CustomObject",
                "fullName": "Appointment__c",
                "label": "Appointment",
                "description": "Appointment custom object",
                "dependencies": [],
                "approval": "PENDING"
            }
        ]
    }

    result = validate_plan(plan)

    assert result.valid is True
    assert result.errors == []


def test_invalid_action():

    plan = {
        "id": "PLAN-002",
        "requirementId": "REQ-002",
        "summary": "Invalid plan",
        "assumptions": [],
        "status": "DRAFT",
        "items": [
            {
                "id": "ITEM-001",
                "action": "MAKE",
                "metadataType": "CustomObject",
                "fullName": "Appointment__c",
                "dependencies": [],
                "approval": "PENDING"
            }
        ]
    }

    result = validate_plan(plan)

    assert result.valid is False
    assert any(
        "invalid action" in error
        for error in result.errors
    )


def test_invalid_metadata_type():

    plan = {
        "id": "PLAN-003",
        "requirementId": "REQ-003",
        "summary": "Invalid metadata",
        "assumptions": [],
        "status": "DRAFT",
        "items": [
            {
                "id": "ITEM-001",
                "action": "CREATE",
                "metadataType": "RandomMetadata",
                "fullName": "Something__c",
                "dependencies": [],
                "approval": "PENDING"
            }
        ]
    }

    result = validate_plan(plan)

    assert result.valid is False