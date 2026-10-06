from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from Backend.AI.app.services.salesforce_capability_registry import (
    SalesforceCapabilityRegistry,
)


# =========================================================
# Allowed Salesforce AI Actions
# =========================================================

ALLOWED_ACTIONS = {
    "CREATE",
    "UPDATE",
    "DELETE",
    "NO_CHANGE",
}


# =========================================================
# Supported / Known Metadata Types
# =========================================================

SUPPORTED_METADATA_TYPES = (
    SalesforceCapabilityRegistry.METADATA_TYPES
)


# =========================================================
# Approval States
# =========================================================

ALLOWED_APPROVAL_STATES = {
    "PENDING",
    "APPROVED",
    "SKIPPED",
    "REJECTED",
}


# =========================================================
# Plan Statuses
# =========================================================

ALLOWED_PLAN_STATUSES = {
    "DRAFT",
    "READY_FOR_REVIEW",
    "APPROVED",
    "REJECTED",
}


# =========================================================
# Validation Result
# =========================================================

class ValidationResult(BaseModel):
    valid: bool

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )


# =========================================================
# Plan Item
# =========================================================

class PlanItem(BaseModel):
    """
    One independently reviewable Salesforce change.

    Extra properties remain allowed because future
    Salesforce metadata types may require additional
    planning information.
    """

    model_config = ConfigDict(
        extra="allow"
    )

    id: str
    action: str
    metadataType: str
    fullName: str

    label: str | None = None
    description: str | None = None

    dependencies: list[str] = Field(
        default_factory=list
    )

    source: Any | None = None
    target: Any | None = None

    config: Any | None = None

    validation: dict[str, Any] | None = None

    approval: str = "PENDING"

    deployment: dict[str, Any] | None = None


# =========================================================
# Complete Implementation Plan
# =========================================================

class ImplementationPlan(BaseModel):
    model_config = ConfigDict(
        extra="allow"
    )

    id: str
    requirementId: str
    summary: str

    assumptions: list[str] = Field(
        default_factory=list
    )

    items: list[PlanItem]

    storyPoints: int | None = None

    status: str = "DRAFT"


# =========================================================
# Common Helpers
# =========================================================

def _non_empty_string(
    value: Any,
) -> bool:

    return (
        isinstance(value, str)
        and bool(value.strip())
    )


def _validate_boolean(
    *,
    item_id: str,
    config: dict[str, Any],
    property_name: str,
    errors: list[str],
) -> None:

    if property_name not in config:
        return

    if not isinstance(
        config[property_name],
        bool,
    ):
        errors.append(
            f"{item_id}: config.{property_name} "
            "must be boolean"
        )


def _validate_integer(
    *,
    item_id: str,
    config: dict[str, Any],
    property_name: str,
    errors: list[str],
    minimum: int | None = None,
    maximum: int | None = None,
) -> None:

    if property_name not in config:
        return

    value = config[property_name]

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        errors.append(
            f"{item_id}: config.{property_name} "
            "must be an integer"
        )
        return

    if (
        minimum is not None
        and value < minimum
    ):
        errors.append(
            f"{item_id}: config.{property_name} "
            f"must be at least {minimum}"
        )

    if (
        maximum is not None
        and value > maximum
    ):
        errors.append(
            f"{item_id}: config.{property_name} "
            f"must not exceed {maximum}"
        )


def _validate_string_list(
    *,
    item_id: str,
    values: Any,
    property_name: str,
    errors: list[str],
    require_non_empty: bool = True,
) -> None:

    if not isinstance(values, list):

        errors.append(
            f"{item_id}: config.{property_name} "
            "must be a list"
        )
        return

    if require_non_empty and not values:

        errors.append(
            f"{item_id}: config.{property_name} "
            "must contain at least one value"
        )
        return

    for value in values:

        if not _non_empty_string(value):

            errors.append(
                f"{item_id}: config.{property_name} "
                "must contain only non-empty strings"
            )
            return

    if len(values) != len(set(values)):

        errors.append(
            f"{item_id}: config.{property_name} "
            "must contain unique values"
        )


# =========================================================
# Custom Field Validation
# =========================================================

def _validate_custom_field(
    item: PlanItem,
    errors: list[str],
    warnings: list[str],
) -> None:

    # -----------------------------------------------------
    # CustomField fullName
    # -----------------------------------------------------

    parts = item.fullName.split(
        ".",
        1,
    )

    if (
        len(parts) != 2
        or not parts[0].strip()
        or not parts[1].strip()
    ):
        errors.append(
            f"{item.id}: CustomField fullName must use "
            "'ObjectApiName.FieldApiName' format"
        )
        return

    # -----------------------------------------------------
    # NO_CHANGE
    # -----------------------------------------------------

    if item.action == "NO_CHANGE":
        return

    # -----------------------------------------------------
    # UPDATE
    #
    # UPDATE uses the change pipeline and may not contain
    # the original field type.
    # -----------------------------------------------------

    if item.action == "UPDATE":

        if item.config is not None:

            if not isinstance(
                item.config,
                dict,
            ):
                errors.append(
                    f"{item.id}: CustomField UPDATE config "
                    "must be an object"
                )

        return

    # -----------------------------------------------------
    # DELETE
    # -----------------------------------------------------

    if item.action == "DELETE":
        return

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    if not isinstance(
        item.config,
        dict,
    ):
        errors.append(
            f"{item.id}: CREATE CustomField requires "
            "a config object"
        )
        return

    config = item.config

    raw_field_type = (
        config.get("fieldType")
        or config.get("type")
    )

    if not raw_field_type:

        errors.append(
            f"{item.id}: CREATE CustomField config "
            "must contain fieldType"
        )
        return

    try:

        field_type = (
            SalesforceCapabilityRegistry
            .normalize_field_type(
                raw_field_type
            )
        )

    except ValueError as exc:

        errors.append(
            f"{item.id}: {exc}"
        )
        return

    # -----------------------------------------------------
    # Known vs executable
    # -----------------------------------------------------

    if not (
        SalesforceCapabilityRegistry
        .is_executable_field_type(
            field_type
        )
    ):

        warnings.append(
            f"{item.id}: field type '{field_type}' is known "
            "but its complete metadata generation pipeline "
            "is not enabled yet"
        )

    # -----------------------------------------------------
    # required
    # -----------------------------------------------------

    _validate_boolean(
        item_id=item.id,
        config=config,
        property_name="required",
        errors=errors,
    )

    # =====================================================
    # Text
    # =====================================================

    if field_type == "Text":

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="length",
            errors=errors,
            minimum=1,
            maximum=255,
        )

    # =====================================================
    # TextArea
    # =====================================================

    elif field_type == "TextArea":

        if "length" in config:
            errors.append(
                f"{item.id}: TextArea must not contain length"
            )

        if "visibleLines" in config:
            errors.append(
                f"{item.id}: TextArea must not contain "
                "visibleLines"
            )

    # =====================================================
    # LongTextArea
    # =====================================================

    elif field_type == "LongTextArea":

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="length",
            errors=errors,
            minimum=256,
            maximum=131072,
        )

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="visibleLines",
            errors=errors,
            minimum=2,
            maximum=50,
        )

    # =====================================================
    # Html / Rich Text
    # =====================================================

    elif field_type == "Html":

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="length",
            errors=errors,
            minimum=256,
            maximum=131072,
        )

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="visibleLines",
            errors=errors,
            minimum=11,
            maximum=50,
        )

    # =====================================================
    # EncryptedText
    # =====================================================

    elif field_type == "EncryptedText":

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="length",
            errors=errors,
            minimum=1,
            maximum=175,
        )

        if "maskChar" in config:

            mask_char = config[
                "maskChar"
            ]

            if mask_char not in {
                "asterisk",
                "x",
                "*",
                "X",
            }:
                errors.append(
                    f"{item.id}: EncryptedText contains "
                    "unsupported maskChar"
                )

        if "maskType" in config:

            mask_type = config[
                "maskType"
            ]

            if mask_type not in {
                "all",
                "creditCard",
                "ssn",
                "lastFour",
                "sin",
                "nino",
            }:
                errors.append(
                    f"{item.id}: EncryptedText contains "
                    "unsupported maskType"
                )

    # =====================================================
    # Picklist
    # =====================================================

    elif field_type == "Picklist":

        values = (
            config.get("picklistValues")
            if "picklistValues" in config
            else config.get("values")
        )

        if values is None:

            errors.append(
                f"{item.id}: Picklist requires "
                "picklistValues"
            )

        else:

            _validate_string_list(
                item_id=item.id,
                values=values,
                property_name="picklistValues",
                errors=errors,
            )

    # =====================================================
    # MultiselectPicklist
    # =====================================================

    elif field_type == "MultiselectPicklist":

        values = (
            config.get("picklistValues")
            if "picklistValues" in config
            else config.get("values")
        )

        if values is None:

            errors.append(
                f"{item.id}: MultiselectPicklist requires "
                "picklistValues"
            )

        else:

            _validate_string_list(
                item_id=item.id,
                values=values,
                property_name="picklistValues",
                errors=errors,
            )

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="visibleLines",
            errors=errors,
            minimum=1,
        )

    # =====================================================
    # Number / Currency / Percent
    # =====================================================

    elif field_type in {
        "Number",
        "Currency",
        "Percent",
    }:

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="precision",
            errors=errors,
            minimum=1,
        )

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="scale",
            errors=errors,
            minimum=0,
        )

        precision = config.get(
            "precision"
        )

        scale = config.get(
            "scale"
        )

        if (
            isinstance(precision, int)
            and not isinstance(precision, bool)
            and isinstance(scale, int)
            and not isinstance(scale, bool)
            and scale > precision
        ):
            errors.append(
                f"{item.id}: scale cannot exceed precision"
            )

    # =====================================================
    # Checkbox
    # =====================================================

    elif field_type == "Checkbox":

        if "defaultValue" in config:

            if not isinstance(
                config["defaultValue"],
                bool,
            ):
                errors.append(
                    f"{item.id}: Checkbox defaultValue "
                    "must be boolean"
                )

    # =====================================================
    # Location / Geolocation
    # =====================================================

    elif field_type == "Location":

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="scale",
            errors=errors,
            minimum=0,
        )

        _validate_boolean(
            item_id=item.id,
            config=config,
            property_name="displayLocationInDecimal",
            errors=errors,
        )

    # =====================================================
    # Relationships
    # =====================================================

    elif field_type in {
        "Lookup",
        "MasterDetail",
        "ExternalLookup",
    }:

        reference_to = config.get(
            "referenceTo"
        )

        if not _non_empty_string(
            reference_to
        ):
            errors.append(
                f"{item.id}: {field_type} requires "
                "referenceTo"
            )

        if "relationshipName" in config:

            if not _non_empty_string(
                config["relationshipName"]
            ):
                errors.append(
                    f"{item.id}: relationshipName must be "
                    "a non-empty string"
                )

        if field_type == "Lookup":

            if "deleteConstraint" in config:

                if not _non_empty_string(
                    config["deleteConstraint"]
                ):
                    errors.append(
                        f"{item.id}: deleteConstraint must "
                        "be a non-empty string"
                    )

        if field_type == "MasterDetail":

            _validate_boolean(
                item_id=item.id,
                config=config,
                property_name="reparentableMasterDetail",
                errors=errors,
            )

            _validate_boolean(
                item_id=item.id,
                config=config,
                property_name="writeRequiresMasterRead",
                errors=errors,
            )

    # =====================================================
    # AutoNumber
    # =====================================================

    elif field_type == "AutoNumber":

        display_format = config.get(
            "displayFormat"
        )

        if not _non_empty_string(
            display_format
        ):
            errors.append(
                f"{item.id}: AutoNumber requires "
                "displayFormat"
            )

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="startingNumber",
            errors=errors,
            minimum=0,
        )

    # =====================================================
    # Formula
    # =====================================================

    elif field_type == "Formula":

        formula = config.get(
            "formula"
        )

        if not _non_empty_string(
            formula
        ):
            errors.append(
                f"{item.id}: Formula requires formula"
            )

        return_type = config.get(
            "formulaReturnType"
        )

        if not _non_empty_string(
            return_type
        ):
            errors.append(
                f"{item.id}: Formula requires "
                "formulaReturnType"
            )

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="precision",
            errors=errors,
            minimum=1,
        )

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="scale",
            errors=errors,
            minimum=0,
        )

        _validate_integer(
            item_id=item.id,
            config=config,
            property_name="length",
            errors=errors,
            minimum=1,
        )

    # =====================================================
    # Roll-Up Summary
    # =====================================================

    elif field_type == "Summary":

        foreign_key = config.get(
            "summaryForeignKey"
        )

        operation = config.get(
            "summaryOperation"
        )

        if not _non_empty_string(
            foreign_key
        ):
            errors.append(
                f"{item.id}: Summary requires "
                "summaryForeignKey"
            )

        if not _non_empty_string(
            operation
        ):
            errors.append(
                f"{item.id}: Summary requires "
                "summaryOperation"
            )

        elif (
            operation.strip().lower()
            != "count"
        ):

            summarized_field = config.get(
                "summarizedField"
            )

            if not _non_empty_string(
                summarized_field
            ):
                errors.append(
                    f"{item.id}: Summary operation "
                    f"'{operation}' requires "
                    "summarizedField"
                )


# =========================================================
# Validation Rule Validation
# =========================================================

def _validate_validation_rule(
    item: PlanItem,
    errors: list[str],
    warnings: list[str],
) -> None:

    if "." not in item.fullName:

        errors.append(
            f"{item.id}: ValidationRule fullName must use "
            "'ObjectApiName.RuleApiName' format"
        )

    if item.action in {
        "NO_CHANGE",
        "DELETE",
    }:
        return

    if not isinstance(
        item.config,
        dict,
    ):
        errors.append(
            f"{item.id}: ValidationRule requires "
            "a config object"
        )
        return

    config = item.config

    if item.action == "CREATE":

        active = config.get(
            "active"
        )

        if not isinstance(
            active,
            bool,
        ):
            errors.append(
                f"{item.id}: ValidationRule requires "
                "boolean active"
            )

        formula = config.get(
            "errorConditionFormula"
        )

        if not _non_empty_string(
            formula
        ):
            errors.append(
                f"{item.id}: ValidationRule requires "
                "errorConditionFormula"
            )

        message = config.get(
            "errorMessage"
        )

        if not _non_empty_string(
            message
        ):
            errors.append(
                f"{item.id}: ValidationRule requires "
                "errorMessage"
            )

        if "errorDisplayField" in config:

            if not _non_empty_string(
                config["errorDisplayField"]
            ):
                errors.append(
                    f"{item.id}: errorDisplayField must be "
                    "a non-empty string"
                )

    if not (
        SalesforceCapabilityRegistry
        .is_executable_metadata_type(
            "ValidationRule"
        )
    ):
        warnings.append(
            f"{item.id}: ValidationRule is known but its "
            "deployment generator is not enabled yet"
        )


# =========================================================
# Flow Validation
# =========================================================

def _validate_flow(
    item: PlanItem,
    errors: list[str],
    warnings: list[str],
) -> None:

    if item.action in {
        "NO_CHANGE",
        "DELETE",
    }:
        return

    if not isinstance(
        item.config,
        dict,
    ):
        errors.append(
            f"{item.id}: Flow requires a config object"
        )
        return

    if item.action == "CREATE":

        flow_type = item.config.get(
            "flowType"
        )

        if not _non_empty_string(
            flow_type
        ):
            errors.append(
                f"{item.id}: Flow requires flowType"
            )

        elif not (
            SalesforceCapabilityRegistry
            .is_valid_flow_type(
                flow_type
            )
        ):
            errors.append(
                f"{item.id}: unsupported flowType "
                f"'{flow_type}'"
            )

    if not (
        SalesforceCapabilityRegistry
        .is_executable_metadata_type(
            "Flow"
        )
    ):
        warnings.append(
            f"{item.id}: Flow is known but its complete "
            "generation pipeline is not enabled yet"
        )


# =========================================================
# Apex Class Validation
# =========================================================

def _validate_apex_class(
    item: PlanItem,
    errors: list[str],
    warnings: list[str],
) -> None:

    if item.action in {
        "NO_CHANGE",
        "DELETE",
    }:
        return

    if not isinstance(
        item.config,
        dict,
    ):
        errors.append(
            f"{item.id}: ApexClass requires a config object"
        )
        return

    if item.action == "CREATE":

        apex_kind = item.config.get(
            "apexKind"
        )

        if not _non_empty_string(
            apex_kind
        ):
            errors.append(
                f"{item.id}: ApexClass requires apexKind"
            )

        elif not (
            SalesforceCapabilityRegistry
            .is_valid_apex_kind(
                apex_kind
            )
        ):
            errors.append(
                f"{item.id}: unsupported apexKind "
                f"'{apex_kind}'"
            )

    if not (
        SalesforceCapabilityRegistry
        .is_executable_metadata_type(
            "ApexClass"
        )
    ):
        warnings.append(
            f"{item.id}: ApexClass is known but code "
            "generation is not enabled yet"
        )


# =========================================================
# Apex Trigger Validation
# =========================================================

def _validate_apex_trigger(
    item: PlanItem,
    errors: list[str],
    warnings: list[str],
) -> None:

    if item.action in {
        "NO_CHANGE",
        "DELETE",
    }:
        return

    if not isinstance(
        item.config,
        dict,
    ):
        errors.append(
            f"{item.id}: ApexTrigger requires "
            "a config object"
        )
        return

    if item.action == "CREATE":

        sobject = item.config.get(
            "sobject"
        )

        if not _non_empty_string(
            sobject
        ):
            errors.append(
                f"{item.id}: ApexTrigger requires sobject"
            )

        events = item.config.get(
            "events"
        )

        if events is None:

            errors.append(
                f"{item.id}: ApexTrigger requires events"
            )

        else:

            _validate_string_list(
                item_id=item.id,
                values=events,
                property_name="events",
                errors=errors,
            )

    if not (
        SalesforceCapabilityRegistry
        .is_executable_metadata_type(
            "ApexTrigger"
        )
    ):
        warnings.append(
            f"{item.id}: ApexTrigger is known but code "
            "generation is not enabled yet"
        )


# =========================================================
# Lightning Web Component Validation
# =========================================================

def _validate_lwc(
    item: PlanItem,
    errors: list[str],
    warnings: list[str],
) -> None:

    if item.action in {
        "NO_CHANGE",
        "DELETE",
    }:
        return

    if not isinstance(
        item.config,
        dict,
    ):
        errors.append(
            f"{item.id}: LightningComponentBundle "
            "requires a config object"
        )
        return

    config = item.config

    if "isExposed" in config:

        if not isinstance(
            config["isExposed"],
            bool,
        ):
            errors.append(
                f"{item.id}: LWC isExposed must be boolean"
            )

    if "targets" in config:

        _validate_string_list(
            item_id=item.id,
            values=config["targets"],
            property_name="targets",
            errors=errors,
            require_non_empty=False,
        )

    if not (
        SalesforceCapabilityRegistry
        .is_executable_metadata_type(
            "LightningComponentBundle"
        )
    ):
        warnings.append(
            f"{item.id}: LightningComponentBundle is known "
            "but LWC generation is not enabled yet"
        )


# =========================================================
# Metadata-Type Specific Validation Router
# =========================================================

def _validate_metadata_item_config(
    item: PlanItem,
    errors: list[str],
    warnings: list[str],
) -> None:

    if item.metadataType == "CustomField":

        _validate_custom_field(
            item,
            errors,
            warnings,
        )

    elif item.metadataType == "ValidationRule":

        _validate_validation_rule(
            item,
            errors,
            warnings,
        )

    elif item.metadataType == "Flow":

        _validate_flow(
            item,
            errors,
            warnings,
        )

    elif item.metadataType == "ApexClass":

        _validate_apex_class(
            item,
            errors,
            warnings,
        )

    elif item.metadataType == "ApexTrigger":

        _validate_apex_trigger(
            item,
            errors,
            warnings,
        )

    elif (
        item.metadataType
        == "LightningComponentBundle"
    ):

        _validate_lwc(
            item,
            errors,
            warnings,
        )

    elif not (
        SalesforceCapabilityRegistry
        .is_executable_metadata_type(
            item.metadataType
        )
    ):

        warnings.append(
            f"{item.id}: metadata type "
            f"'{item.metadataType}' is known but its "
            "complete generation pipeline is not enabled yet"
        )


# =========================================================
# Validate Salesforce Implementation Plan
# =========================================================

def validate_plan(
    plan_data: dict,
) -> ValidationResult:

    errors: list[str] = []
    warnings: list[str] = []

    # =====================================================
    # Pydantic Structure
    # =====================================================

    try:

        plan = (
            ImplementationPlan
            .model_validate(
                plan_data
            )
        )

    except Exception as exc:

        return ValidationResult(
            valid=False,
            errors=[
                f"Invalid plan structure: {exc}"
            ],
        )

    # =====================================================
    # Plan-Level Validation
    # =====================================================

    if not plan.id.strip():

        errors.append(
            "Plan id cannot be empty"
        )

    if not plan.requirementId.strip():

        errors.append(
            "requirementId cannot be empty"
        )

    if not plan.summary.strip():

        errors.append(
            "Plan summary cannot be empty"
        )

    if plan.status not in ALLOWED_PLAN_STATUSES:

        errors.append(
            f"Invalid plan status: {plan.status}"
        )

    if (
        plan.storyPoints is not None
        and plan.storyPoints < 0
    ):
        errors.append(
            "storyPoints cannot be negative"
        )

    # =====================================================
    # Duplicate Item IDs
    # =====================================================

    item_ids = [
        item.id
        for item in plan.items
    ]

    duplicate_ids = {
        item_id
        for item_id in item_ids
        if item_ids.count(item_id) > 1
    }

    for duplicate_id in sorted(
        duplicate_ids
    ):

        errors.append(
            f"Duplicate plan item ID: "
            f"{duplicate_id}"
        )

    # =====================================================
    # Individual Items
    # =====================================================

    for item in plan.items:

        # -------------------------------------------------
        # ID
        # -------------------------------------------------

        if not item.id.strip():

            errors.append(
                "Plan item id cannot be empty"
            )

        # -------------------------------------------------
        # Action
        # -------------------------------------------------

        if item.action not in ALLOWED_ACTIONS:

            errors.append(
                f"{item.id}: invalid action "
                f"'{item.action}'"
            )

        # -------------------------------------------------
        # Metadata Type
        # -------------------------------------------------

        if not (
            SalesforceCapabilityRegistry
            .is_known_metadata_type(
                item.metadataType
            )
        ):

            errors.append(
                f"{item.id}: unsupported metadata type "
                f"'{item.metadataType}'"
            )

        # -------------------------------------------------
        # Approval
        # -------------------------------------------------

        if (
            item.approval
            not in ALLOWED_APPROVAL_STATES
        ):

            errors.append(
                f"{item.id}: invalid approval state "
                f"'{item.approval}'"
            )

        # -------------------------------------------------
        # fullName
        # -------------------------------------------------

        if not item.fullName.strip():

            errors.append(
                f"{item.id}: fullName cannot be empty"
            )

        # -------------------------------------------------
        # Dependencies
        # -------------------------------------------------

        for dependency in item.dependencies:

            if not _non_empty_string(
                dependency
            ):

                errors.append(
                    f"{item.id}: dependency cannot be empty"
                )
                continue

            if dependency == item.id:

                errors.append(
                    f"{item.id}: cannot depend on itself"
                )

            elif dependency not in item_ids:

                warnings.append(
                    f"{item.id}: dependency '{dependency}' "
                    "is not another plan item; it must exist "
                    "in Salesforce context"
                )

        # -------------------------------------------------
        # Metadata-specific config validation
        # -------------------------------------------------

        if (
            SalesforceCapabilityRegistry
            .is_known_metadata_type(
                item.metadataType
            )
        ):

            _validate_metadata_item_config(
                item,
                errors,
                warnings,
            )

    # =====================================================
    # Circular Dependency Detection
    # =====================================================

    dependency_map = {
        item.id: item.dependencies
        for item in plan.items
    }

    def has_cycle(
        current: str,
        visiting: set[str],
        visited: set[str],
    ) -> bool:

        if current in visiting:
            return True

        if current in visited:
            return False

        visiting.add(
            current
        )

        for dependency in dependency_map.get(
            current,
            [],
        ):

            if dependency not in dependency_map:
                continue

            if has_cycle(
                dependency,
                visiting,
                visited,
            ):
                return True

        visiting.remove(
            current
        )

        visited.add(
            current
        )

        return False

    visited: set[str] = set()

    for item_id in dependency_map:

        if has_cycle(
            item_id,
            set(),
            visited,
        ):

            errors.append(
                "Circular dependency detected in plan"
            )
            break

    # =====================================================
    # Action Semantics
    # =====================================================

    for item in plan.items:

        # -------------------------------------------------
        # NO_CHANGE
        # -------------------------------------------------

        if item.action == "NO_CHANGE":

            if item.target is not None:

                warnings.append(
                    f"{item.id}: NO_CHANGE item contains "
                    "target data"
                )

        # -------------------------------------------------
        # CREATE
        # -------------------------------------------------

        elif item.action == "CREATE":

            if item.source is not None:

                warnings.append(
                    f"{item.id}: CREATE item contains "
                    "source data"
                )

        # -------------------------------------------------
        # UPDATE
        # -------------------------------------------------

        elif item.action == "UPDATE":

            if (
                item.source is None
                and item.target is None
                and item.config is None
            ):

                warnings.append(
                    f"{item.id}: UPDATE item does not "
                    "describe source, target, or config"
                )

    # =====================================================
    # Final Result
    # =====================================================

    return ValidationResult(
        valid=(
            len(errors) == 0
        ),
        errors=errors,
        warnings=warnings,
    )