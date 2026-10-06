import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    model_validator,
)


# ==================================================
# Constants
# ==================================================

SUPPORTED_METADATA_TYPES = {
    "CustomObject",
    "CustomField",
}

SUPPORTED_VALIDATION_CODES = {
    "PLAN_NOT_APPROVED",
    "ITEM_NOT_APPROVED",
    "METADATA_NOT_FOUND",
    "INSUFFICIENT_CONTEXT",
    "UNSUPPORTED_ACTION",
    "UNSUPPORTED_METADATA_TYPE",
    "UNSUPPORTED_FIELD_TYPE_CHANGE",
    "UNSUPPORTED_RENAME",
    "UNSUPPORTED_CHANGE",
    "NO_CHANGE_REQUIRED",
    "INVALID_FULL_NAME",
    "UNRESOLVED_DEPENDENCY",
}


CUSTOM_OBJECT_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*__c$"
)

CUSTOM_FIELD_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:__c)?"
    r"\.[A-Za-z][A-Za-z0-9_]*__c$"
)


# ==================================================
# Validation Issue
# ==================================================

class ChangeValidationIssue(BaseModel):

    code: str
    itemId: str | None = None
    message: str

    @model_validator(mode="after")
    def validate_issue(self):

        if self.code not in SUPPORTED_VALIDATION_CODES:

            raise ValueError(
                f"Unsupported validation issue code: "
                f"{self.code}"
            )

        if not self.message.strip():

            raise ValueError(
                "Validation issue message cannot be empty."
            )

        return self


# ==================================================
# Change Item
# ==================================================

class ChangeItem(BaseModel):

    itemId: str

    action: Literal["UPDATE"]

    metadataType: Literal[
        "CustomObject",
        "CustomField",
    ]

    fullName: str

    dependencies: list[str] = Field(
        default_factory=list
    )

    changes: dict[str, Any]

    @model_validator(mode="after")
    def validate_change_item(self):

        if not self.itemId.strip():

            raise ValueError(
                "itemId cannot be empty."
            )

        if not self.fullName.strip():

            raise ValueError(
                "fullName cannot be empty."
            )

        if len(
            self.dependencies
        ) != len(
            set(self.dependencies)
        ):

            raise ValueError(
                f"Duplicate dependencies found for "
                f"{self.itemId}."
            )

        for dependency in self.dependencies:

            if not dependency.strip():

                raise ValueError(
                    f"Empty dependency found for "
                    f"{self.itemId}."
                )

        if not self.changes:

            raise ValueError(
                f"Change item {self.itemId} must "
                f"contain at least one change."
            )

        if self.metadataType == "CustomObject":

            self._validate_custom_object_change()

        elif self.metadataType == "CustomField":

            self._validate_custom_field_change()

        return self

    # ==================================================
    # Custom Object Validation
    # ==================================================

    def _validate_custom_object_change(self):

        if not CUSTOM_OBJECT_PATTERN.fullmatch(
            self.fullName
        ):

            raise ValueError(
                f"Invalid CustomObject fullName: "
                f"{self.fullName}"
            )

        allowed_changes = {
            "label",
            "pluralLabel",
        }

        unknown_changes = (
            set(self.changes.keys())
            - allowed_changes
        )

        if unknown_changes:

            raise ValueError(
                "Unsupported CustomObject change(s): "
                + ", ".join(
                    sorted(unknown_changes)
                )
            )

        for property_name in (
            "label",
            "pluralLabel",
        ):

            if property_name in self.changes:

                self._validate_string_change(
                    property_name,
                    self.changes[property_name],
                )

    # ==================================================
    # Custom Field Validation
    # ==================================================

    def _validate_custom_field_change(self):

        if not CUSTOM_FIELD_PATTERN.fullmatch(
            self.fullName
        ):

            raise ValueError(
                f"Invalid CustomField fullName: "
                f"{self.fullName}"
            )

        allowed_changes = {
            "label",
            "required",
            "addPicklistValues",
        }

        unknown_changes = (
            set(self.changes.keys())
            - allowed_changes
        )

        if unknown_changes:

            raise ValueError(
                "Unsupported CustomField change(s): "
                + ", ".join(
                    sorted(unknown_changes)
                )
            )

        if "label" in self.changes:

            self._validate_string_change(
                "label",
                self.changes["label"],
            )

        if "required" in self.changes:

            self._validate_boolean_change(
                "required",
                self.changes["required"],
            )

        if "addPicklistValues" in self.changes:

            self._validate_picklist_values(
                self.changes[
                    "addPicklistValues"
                ]
            )

    # ==================================================
    # Shared Property Validators
    # ==================================================

    @staticmethod
    def _validate_string_change(
        property_name: str,
        value: Any,
    ):

        if not isinstance(
            value,
            dict,
        ):

            raise ValueError(
                f"{property_name} change must "
                f"be an object."
            )

        if set(value.keys()) != {
            "from",
            "to",
        }:

            raise ValueError(
                f"{property_name} change must "
                f"contain exactly 'from' and 'to'."
            )

        old_value = value["from"]
        new_value = value["to"]

        if not isinstance(
            old_value,
            str,
        ):

            raise ValueError(
                f"{property_name}.from must "
                f"be a string."
            )

        if not isinstance(
            new_value,
            str,
        ):

            raise ValueError(
                f"{property_name}.to must "
                f"be a string."
            )

        if not old_value.strip():

            raise ValueError(
                f"{property_name}.from cannot "
                f"be empty."
            )

        if not new_value.strip():

            raise ValueError(
                f"{property_name}.to cannot "
                f"be empty."
            )

        if old_value == new_value:

            raise ValueError(
                f"{property_name} does not "
                f"contain an actual change."
            )

    @staticmethod
    def _validate_boolean_change(
        property_name: str,
        value: Any,
    ):

        if not isinstance(
            value,
            dict,
        ):

            raise ValueError(
                f"{property_name} change must "
                f"be an object."
            )

        if set(value.keys()) != {
            "from",
            "to",
        }:

            raise ValueError(
                f"{property_name} change must "
                f"contain exactly 'from' and 'to'."
            )

        old_value = value["from"]
        new_value = value["to"]

        if not isinstance(
            old_value,
            bool,
        ):

            raise ValueError(
                f"{property_name}.from must "
                f"be a boolean."
            )

        if not isinstance(
            new_value,
            bool,
        ):

            raise ValueError(
                f"{property_name}.to must "
                f"be a boolean."
            )

        if old_value == new_value:

            raise ValueError(
                f"{property_name} does not "
                f"contain an actual change."
            )

    @staticmethod
    def _validate_picklist_values(
        values: Any,
    ):

        if not isinstance(
            values,
            list,
        ):

            raise ValueError(
                "addPicklistValues must be a list."
            )

        if not values:

            raise ValueError(
                "addPicklistValues must contain "
                "at least one value."
            )

        for value in values:

            if not isinstance(
                value,
                str,
            ):

                raise ValueError(
                    "Every picklist value must "
                    "be a string."
                )

            if not value.strip():

                raise ValueError(
                    "Picklist values cannot be empty."
                )

        if len(values) != len(set(values)):

            raise ValueError(
                "Duplicate values are not allowed "
                "in addPicklistValues."
            )


# ==================================================
# Change Specification
# ==================================================

class ChangeSpecification(BaseModel):

    planId: str

    changes: list[ChangeItem] = Field(
        default_factory=list
    )

    validationIssues: list[
        ChangeValidationIssue
    ] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_specification(self):

        if not self.planId.strip():

            raise ValueError(
                "planId cannot be empty."
            )

        item_ids = [
            item.itemId
            for item in self.changes
        ]

        if len(
            item_ids
        ) != len(
            set(item_ids)
        ):

            raise ValueError(
                "Duplicate change itemId values "
                "are not allowed."
            )

        return self


# ==================================================
# Validation Result
# ==================================================

class ChangeSpecValidationResult(BaseModel):

    valid: bool

    specification: (
        ChangeSpecification | None
    ) = None

    errors: list[str] = Field(
        default_factory=list
    )


# ==================================================
# Main Validation Function
# ==================================================

def validate_change_spec(
    data: dict,
) -> ChangeSpecValidationResult:
    """
    Validate an AI-generated Salesforce
    Change Specification.

    Returns a structured validation result instead
    of allowing Pydantic ValidationError to escape.
    """

    if not isinstance(
        data,
        dict,
    ):

        return ChangeSpecValidationResult(
            valid=False,
            specification=None,
            errors=[
                (
                    "Change specification must "
                    "be a JSON object."
                )
            ],
        )

    try:

        specification = (
            ChangeSpecification.model_validate(
                data
            )
        )

        return ChangeSpecValidationResult(
            valid=True,
            specification=specification,
            errors=[],
        )

    except ValidationError as exc:

        errors = []

        for error in exc.errors():

            location = ".".join(
                str(part)
                for part in error.get(
                    "loc",
                    [],
                )
            )

            message = error.get(
                "msg",
                "Validation failed.",
            )

            if location:

                errors.append(
                    f"{location}: {message}"
                )

            else:

                errors.append(
                    message
                )

        return ChangeSpecValidationResult(
            valid=False,
            specification=None,
            errors=errors,
        )

    except ValueError as exc:

        return ChangeSpecValidationResult(
            valid=False,
            specification=None,
            errors=[
                str(exc)
            ],
        )