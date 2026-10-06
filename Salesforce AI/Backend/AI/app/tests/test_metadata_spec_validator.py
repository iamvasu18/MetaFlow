

from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
    validate_metadata_spec,
)


# =========================================================
# Helper
# =========================================================

def build_valid_spec():

    return {
        "planId": "PLAN-TEST-001",
        "metadata": [
            {
                "itemId": "ITEM-001",
                "action": "CREATE",
                "metadataType": "CustomObject",
                "fullName": "TrainingSession__c",
                "label": "Training Session",
                "description": None,
                "dependencies": [],
                "config": {},
            },
            {
                "itemId": "ITEM-002",
                "action": "CREATE",
                "metadataType": "CustomField",
                "fullName": "TrainingSession__c.Status__c",
                "label": "Status",
                "description": None,
                "dependencies": [
                    "ITEM-001"
                ],
                "config": {
                    "type": "Picklist",
                    "values": [
                        "Scheduled",
                        "Completed",
                        "Cancelled",
                    ],
                },
            },
        ],
        "validationIssues": [],
    }


# =========================================================
# Valid Specification
# =========================================================

def test_valid_metadata_specification():

    data = build_valid_spec()

    result = validate_metadata_spec(
        data
    )

    assert result.valid is True
    assert result.errors == []


def test_metadata_specification_model():

    data = build_valid_spec()

    specification = (
        MetadataSpecification.model_validate(
            data
        )
    )

    assert (
        specification.planId
        == "PLAN-TEST-001"
    )

    assert len(
        specification.metadata
    ) == 2


# =========================================================
# Invalid Input
# =========================================================

def test_rejects_non_dictionary():

    result = validate_metadata_spec(
        "invalid"
    )

    assert result.valid is False

    assert (
        "dictionary"
        in result.errors[0]
    )


def test_rejects_empty_plan_id():

    data = build_valid_spec()

    data["planId"] = ""

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


# =========================================================
# Action Validation
# =========================================================

def test_rejects_update_action():

    data = build_valid_spec()

    data["metadata"][0][
        "action"
    ] = "UPDATE"

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


def test_rejects_delete_action():

    data = build_valid_spec()

    data["metadata"][0][
        "action"
    ] = "DELETE"

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


# =========================================================
# Metadata Type Validation
# =========================================================

def test_rejects_unsupported_metadata_type():

    data = build_valid_spec()

    data["metadata"][0][
        "metadataType"
    ] = "Flow"

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


# =========================================================
# Custom Object Validation
# =========================================================

def test_rejects_invalid_custom_object_full_name():

    data = build_valid_spec()

    data["metadata"][0][
        "fullName"
    ] = "TrainingSession__c.Name__c"

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


def test_rejects_invalid_sharing_model():

    data = build_valid_spec()

    data["metadata"][0][
        "config"
    ] = {
        "sharingModel": "Private"
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


# =========================================================
# Custom Field Validation
# =========================================================

def test_valid_text_field():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Text",
        "required": True,
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is True


def test_valid_email_field():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Email"
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is True


def test_valid_date_field():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Date"
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is True


def test_rejects_field_without_type():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {}

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


def test_rejects_unsupported_field_type():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Number"
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


# =========================================================
# Picklist Validation
# =========================================================

def test_rejects_picklist_without_values():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Picklist"
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


def test_rejects_empty_picklist():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Picklist",
        "values": [],
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


def test_rejects_duplicate_picklist_values():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Picklist",
        "values": [
            "Scheduled",
            "Scheduled",
        ],
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


def test_rejects_non_string_picklist_value():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Picklist",
        "values": [
            "Scheduled",
            123,
        ],
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


def test_rejects_values_for_text_field():

    data = build_valid_spec()

    data["metadata"][1][
        "config"
    ] = {
        "type": "Text",
        "values": [
            "One",
            "Two",
        ],
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


# =========================================================
# Duplicate Item Validation
# =========================================================

def test_rejects_duplicate_item_ids():

    data = build_valid_spec()

    data["metadata"][1][
        "itemId"
    ] = "ITEM-001"

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False


# =========================================================
# Validation Issue Tests
# =========================================================

def test_accepts_validation_issue():

    data = {
        "planId": "PLAN-TEST-002",
        "metadata": [],
        "validationIssues": [
            {
                "itemId": "ITEM-001",
                "code": "UNSUPPORTED_ACTION",
                "message": (
                    "UPDATE is not supported "
                    "by metadata specification v001."
                ),
            }
        ],
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is True


def test_rejects_unknown_validation_code():

    data = {
        "planId": "PLAN-TEST-003",
        "metadata": [],
        "validationIssues": [
            {
                "itemId": "ITEM-001",
                "code": "UNKNOWN_ERROR",
                "message": "Unknown error.",
            }
        ],
    }

    result = validate_metadata_spec(
        data
    )

    assert result.valid is False