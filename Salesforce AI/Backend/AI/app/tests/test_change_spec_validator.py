from Backend.AI.app.validators.change_spec_validator import (
    ChangeSpecification,
    validate_change_spec,
)


# ==================================================
# Helpers
# ==================================================

def build_valid_picklist_change():
    return {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomField",
                "fullName": (
                    "AI_Test_Session__c.Status__c"
                ),
                "dependencies": [
                    "AI_Test_Session__c"
                ],
                "changes": {
                    "addPicklistValues": [
                        "Cancelled"
                    ]
                },
            }
        ],
        "validationIssues": [],
    }


# ==================================================
# Valid Specification Tests
# ==================================================

def test_valid_picklist_change():

    data = build_valid_picklist_change()

    result = validate_change_spec(
        data
    )

    assert result.valid is True
    assert result.specification is not None
    assert result.errors == []

    assert (
        result.specification.planId
        == "PLAN-002"
    )

    assert (
        len(
            result.specification.changes
        )
        == 1
    )


def test_valid_object_label_change():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomObject",
                "fullName": "Project__c",
                "dependencies": [],
                "changes": {
                    "label": {
                        "from": "Project",
                        "to": "Customer Project",
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is True
    assert result.specification is not None


def test_valid_object_plural_label_change():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomObject",
                "fullName": "Project__c",
                "dependencies": [],
                "changes": {
                    "pluralLabel": {
                        "from": "Projects",
                        "to": "Customer Projects",
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is True


def test_valid_field_label_change():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomField",
                "fullName": (
                    "Project__c.Status__c"
                ),
                "dependencies": [
                    "Project__c"
                ],
                "changes": {
                    "label": {
                        "from": "Status",
                        "to": "Project Status",
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is True


def test_valid_required_change():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomField",
                "fullName": (
                    "Customer__c.Email__c"
                ),
                "dependencies": [
                    "Customer__c"
                ],
                "changes": {
                    "required": {
                        "from": False,
                        "to": True,
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is True


def test_valid_multiple_picklist_values():

    data = build_valid_picklist_change()

    data["changes"][0]["changes"][
        "addPicklistValues"
    ] = [
        "Cancelled",
        "Paused",
    ]

    result = validate_change_spec(
        data
    )

    assert result.valid is True


# ==================================================
# Invalid Action Tests
# ==================================================

def test_reject_create_action():

    data = build_valid_picklist_change()

    data["changes"][0][
        "action"
    ] = "CREATE"

    result = validate_change_spec(
        data
    )

    assert result.valid is False
    assert result.specification is None
    assert len(result.errors) > 0


def test_reject_delete_action():

    data = build_valid_picklist_change()

    data["changes"][0][
        "action"
    ] = "DELETE"

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# Metadata Type Tests
# ==================================================

def test_reject_unsupported_metadata_type():

    data = build_valid_picklist_change()

    data["changes"][0][
        "metadataType"
    ] = "ApexClass"

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# API Name Tests
# ==================================================

def test_reject_invalid_custom_object_full_name():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomObject",
                "fullName": "Project",
                "dependencies": [],
                "changes": {
                    "label": {
                        "from": "Project",
                        "to": "Customer Project",
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_invalid_custom_field_full_name():

    data = build_valid_picklist_change()

    data["changes"][0][
        "fullName"
    ] = "Status__c"

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# Unsupported Change Tests
# ==================================================

def test_reject_field_type_change():

    data = build_valid_picklist_change()

    data["changes"][0]["changes"] = {
        "type": {
            "from": "Email",
            "to": "Text",
        }
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_object_unknown_change():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomObject",
                "fullName": "Project__c",
                "dependencies": [],
                "changes": {
                    "sharingModel": {
                        "from": "Read",
                        "to": "ReadWrite",
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# No-Change Tests
# ==================================================

def test_reject_same_label_value():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomField",
                "fullName": (
                    "Project__c.Status__c"
                ),
                "dependencies": [
                    "Project__c"
                ],
                "changes": {
                    "label": {
                        "from": "Status",
                        "to": "Status",
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_same_required_value():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomField",
                "fullName": (
                    "Customer__c.Email__c"
                ),
                "dependencies": [
                    "Customer__c"
                ],
                "changes": {
                    "required": {
                        "from": True,
                        "to": True,
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# Picklist Tests
# ==================================================

def test_reject_empty_picklist_values():

    data = build_valid_picklist_change()

    data["changes"][0]["changes"][
        "addPicklistValues"
    ] = []

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_duplicate_picklist_values():

    data = build_valid_picklist_change()

    data["changes"][0]["changes"][
        "addPicklistValues"
    ] = [
        "Cancelled",
        "Cancelled",
    ]

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_empty_picklist_value():

    data = build_valid_picklist_change()

    data["changes"][0]["changes"][
        "addPicklistValues"
    ] = [
        ""
    ]

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_non_string_picklist_value():

    data = build_valid_picklist_change()

    data["changes"][0]["changes"][
        "addPicklistValues"
    ] = [
        "Cancelled",
        100,
    ]

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# Change Structure Tests
# ==================================================

def test_reject_empty_changes():

    data = build_valid_picklist_change()

    data["changes"][0][
        "changes"
    ] = {}

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_invalid_label_structure():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomField",
                "fullName": (
                    "Project__c.Status__c"
                ),
                "dependencies": [
                    "Project__c"
                ],
                "changes": {
                    "label": {
                        "to": "Project Status"
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_invalid_required_structure():

    data = {
        "planId": "PLAN-002",
        "changes": [
            {
                "itemId": "ITEM-001",
                "action": "UPDATE",
                "metadataType": "CustomField",
                "fullName": (
                    "Customer__c.Email__c"
                ),
                "dependencies": [
                    "Customer__c"
                ],
                "changes": {
                    "required": {
                        "from": False,
                        "to": "true",
                    }
                },
            }
        ],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# Dependency Tests
# ==================================================

def test_reject_duplicate_dependencies():

    data = build_valid_picklist_change()

    data["changes"][0][
        "dependencies"
    ] = [
        "AI_Test_Session__c",
        "AI_Test_Session__c",
    ]

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_empty_dependency():

    data = build_valid_picklist_change()

    data["changes"][0][
        "dependencies"
    ] = [
        ""
    ]

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# Duplicate Item Tests
# ==================================================

def test_reject_duplicate_item_ids():

    data = build_valid_picklist_change()

    second_item = {
        "itemId": "ITEM-001",
        "action": "UPDATE",
        "metadataType": "CustomField",
        "fullName": (
            "AI_Test_Session__c."
            "Session_Date__c"
        ),
        "dependencies": [
            "AI_Test_Session__c"
        ],
        "changes": {
            "label": {
                "from": "Session Date",
                "to": "Start Date",
            }
        },
    }

    data["changes"].append(
        second_item
    )

    result = validate_change_spec(
        data
    )

    assert result.valid is False


# ==================================================
# Validation Issue Tests
# ==================================================

def test_valid_validation_issue():

    data = {
        "planId": "PLAN-002",
        "changes": [],
        "validationIssues": [
            {
                "code": (
                    "METADATA_NOT_FOUND"
                ),
                "itemId": "ITEM-001",
                "message": (
                    "Existing Salesforce metadata "
                    "could not be found."
                ),
            }
        ],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is True
    assert result.specification is not None

    assert (
        len(
            result.specification
            .validationIssues
        )
        == 1
    )


def test_reject_unknown_validation_issue_code():

    data = {
        "planId": "PLAN-002",
        "changes": [],
        "validationIssues": [
            {
                "code": "UNKNOWN_ERROR",
                "itemId": "ITEM-001",
                "message": "Something failed.",
            }
        ],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_allow_null_item_id_for_plan_issue():

    data = {
        "planId": "PLAN-002",
        "changes": [],
        "validationIssues": [
            {
                "code": (
                    "PLAN_NOT_APPROVED"
                ),
                "itemId": None,
                "message": (
                    "Implementation plan must "
                    "be approved."
                ),
            }
        ],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is True


# ==================================================
# Top-Level Tests
# ==================================================

def test_reject_empty_plan_id():

    data = build_valid_picklist_change()

    data["planId"] = ""

    result = validate_change_spec(
        data
    )

    assert result.valid is False


def test_reject_non_object_input():

    result = validate_change_spec(
        ["invalid"]
    )

    assert result.valid is False
    assert result.specification is None

    assert len(
        result.errors
    ) > 0


def test_empty_change_list_is_allowed():

    data = {
        "planId": "PLAN-002",
        "changes": [],
        "validationIssues": [],
    }

    result = validate_change_spec(
        data
    )

    assert result.valid is True


# ==================================================
# Model Creation Test
# ==================================================

def test_change_specification_model_creation():

    data = build_valid_picklist_change()

    specification = (
        ChangeSpecification.model_validate(
            data
        )
    )

    assert (
        specification.planId
        == "PLAN-002"
    )

    assert (
        specification
        .changes[0]
        .metadataType
        == "CustomField"
    )

    assert (
        specification
        .changes[0]
        .action
        == "UPDATE"
    )