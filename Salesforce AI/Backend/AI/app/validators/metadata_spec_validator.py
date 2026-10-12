from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from Backend.AI.app.services.salesforce_capability_registry import (
    SalesforceCapabilityRegistry,
)
from Backend.AI.app.services.apex_validator import validate_apex_source


# =========================================================
# Supported values - Metadata Specification v001
# =========================================================

SUPPORTED_ACTION = "CREATE"

# Phase 1 executable metadata-spec families.
#
# Apex / LWC / application metadata are intentionally
# not accepted here yet. They are known by the capability
# registry and planning layer, but each will receive its own
# metadata/code specification and generator in later phases.
SUPPORTED_METADATA_TYPES = {
    "CustomObject",
    "CustomField",
    "ValidationRule",
    "Flow",
    "PermissionSet",
    "ApexClass",
    "ApexTrigger",
}

SUPPORTED_FIELD_TYPES = set(
    SalesforceCapabilityRegistry.FIELD_TYPES
)

SUPPORTED_VALIDATION_CODES = {
    "PLAN_NOT_APPROVED",
    "ITEM_NOT_APPROVED",
    "UNSUPPORTED_ACTION",
    "UNSUPPORTED_METADATA_TYPE",
    "UNSUPPORTED_FIELD_TYPE",
    "MISSING_CONFIGURATION",
    "INVALID_FULL_NAME",
    "UNRESOLVED_DEPENDENCY",
}

FORMULA_RETURN_TYPES = {
    "Checkbox",
    "Currency",
    "Date",
    "DateTime",
    "Number",
    "Percent",
    "Text",
    "Time",
}

SUMMARY_OPERATIONS = {
    "Count",
    "Min",
    "Max",
    "Sum",
}

LOOKUP_DELETE_CONSTRAINTS = {
    "SetNull",
    "Restrict",
    "Cascade",
}

ENCRYPTED_MASK_TYPES = {
    "all",
    "creditCard",
    "ssn",
    "lastFour",
    "sin",
    "nino",
}

ENCRYPTED_MASK_CHARS = {
    "*",
    "asterisk",
    "x",
    "X",
}


# =========================================================
# Validation Issue
# =========================================================

class MetadataValidationIssue(BaseModel):
    """
    Represents an issue discovered while converting
    an approved plan into metadata specifications.
    """

    itemId: str | None = None

    code: Literal[
        "PLAN_NOT_APPROVED",
        "ITEM_NOT_APPROVED",
        "UNSUPPORTED_ACTION",
        "UNSUPPORTED_METADATA_TYPE",
        "UNSUPPORTED_FIELD_TYPE",
        "MISSING_CONFIGURATION",
        "INVALID_FULL_NAME",
        "UNRESOLVED_DEPENDENCY",
    ]

    message: str = Field(
        min_length=1
    )


# =========================================================
# Metadata Item
# =========================================================

class MetadataItem(BaseModel):
    """
    One Salesforce metadata component that can be passed to
    the deterministic metadata generation layer.

    This v001 validator supports CREATE for:

    - CustomObject
    - CustomField
    - ValidationRule
    - Flow (strict supported trigger/resource contracts)
    - ApexClass and ApexTrigger (local checks; Salesforce compilation required)

    Planning may know about additional Salesforce component
    types, but those types must not enter this specification
    until their deterministic generation pipeline exists.
    """

    itemId: str = Field(
        min_length=1
    )

    action: Literal["CREATE"]

    metadataType: Literal[
        "CustomObject",
        "CustomField",
        "ValidationRule",
        "Flow",
        "PermissionSet",
        "ApexClass",
        "ApexTrigger",
    ]

    fullName: str = Field(
        min_length=1
    )

    label: str | None = None

    description: str | None = None

    dependencies: list[str] = Field(
        default_factory=list
    )

    config: dict[str, Any] = Field(
        default_factory=dict
    )

    # -----------------------------------------------------
    # Metadata-specific validation
    # -----------------------------------------------------

    @model_validator(mode="after")
    def validate_metadata_item(
        self,
    ):
        from Backend.AI.app.services.metadata_safety import validate_component_name
        validate_component_name(self.metadataType, self.fullName)
        if self.metadataType == "CustomObject":
            self._validate_custom_object()

        elif self.metadataType == "CustomField":
            self._validate_custom_field()

        elif self.metadataType == "ValidationRule":
            self._validate_validation_rule()

        elif self.metadataType == "PermissionSet":
            from Backend.AI.app.services.permission_set_service import validate_permission_set
            validate_permission_set(self.fullName, self.label, self.config)

        elif self.metadataType == "Flow":
            from Backend.AI.app.validators.flow_validator import validate_flow
            validate_flow(self.fullName, self.label, self.config)

        elif self.metadataType in {"ApexClass", "ApexTrigger"}:
            self._validate_apex()

        return self

    def _validate_apex(self) -> None:
        allowed = {"apexKind", "body"} if self.metadataType == "ApexClass" else {"sobject", "events", "body"}
        unsupported = set(self.config.keys()) - allowed
        if unsupported:
            raise ValueError(
                f"Unsupported {self.metadataType} config: "
                + ", ".join(sorted(unsupported))
            )
        errors, _warnings = validate_apex_source(
            self.metadataType,
            self.fullName,
            self.config,
        )
        if errors:
            raise ValueError(
                f"{self.metadataType} validation failed: "
                + "; ".join(errors)
            )

    # =====================================================
    # Generic helpers
    # =====================================================

    @staticmethod
    def _require_non_empty_string(
        value: Any,
        message: str,
    ) -> str:
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                message
            )

        return value.strip()

    @staticmethod
    def _validate_boolean(
        value: Any,
        message: str,
    ) -> None:
        if not isinstance(
            value,
            bool,
        ):
            raise ValueError(
                message
            )

    @staticmethod
    def _validate_integer_range(
        value: Any,
        minimum: int,
        maximum: int,
        message: str,
    ) -> int:
        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                message
            )

        try:
            parsed_value = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                message
            ) from exc

        if not (
            minimum
            <= parsed_value
            <= maximum
        ):
            raise ValueError(
                message
            )

        return parsed_value

    @staticmethod
    def _validate_positive_integer(
        value: Any,
        message: str,
    ) -> int:
        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                message
            )

        try:
            parsed_value = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                message
            ) from exc

        if parsed_value < 1:
            raise ValueError(
                message
            )

        return parsed_value

    @staticmethod
    def _validate_picklist_values(
        values: Any,
        field_type: str,
    ) -> None:
        if (
            not isinstance(values, list)
            or not values
        ):
            raise ValueError(
                f"{field_type} field must contain "
                "at least one value."
            )

        normalized_values: list[str] = []

        for value in values:
            if (
                not isinstance(value, str)
                or not value.strip()
            ):
                raise ValueError(
                    f"{field_type} values must be "
                    "non-empty strings."
                )

            normalized_values.append(
                value.strip()
            )

        if len(
            normalized_values
        ) != len(
            set(normalized_values)
        ):
            raise ValueError(
                f"{field_type} values must be unique."
            )

    # =====================================================
    # Custom Object validation
    # =====================================================

    def _validate_custom_object(
        self,
    ) -> None:
        if "." in self.fullName:
            raise ValueError(
                "CustomObject fullName must contain "
                "only the object API name."
            )

        allowed_config = {
            "enableReports",
            "pluralLabel",
            "nameFieldLabel",
            "nameFieldType",
            "deploymentStatus",
            "sharingModel",
        }

        unsupported = (
            set(
                self.config.keys()
            )
            - allowed_config
        )

        if unsupported:
            raise ValueError(
                "Unsupported CustomObject config: "
                + ", ".join(
                    sorted(
                        unsupported
                    )
                )
            )

        if "enableReports" in self.config and not isinstance(self.config["enableReports"], bool):
            raise ValueError("CustomObject enableReports must be boolean.")

        name_field_type = self.config.get(
            "nameFieldType"
        )

        if (
            name_field_type is not None
            and name_field_type != "Text"
        ):
            raise ValueError(
                "CustomObject nameFieldType "
                "must be Text."
            )

        deployment_status = self.config.get(
            "deploymentStatus"
        )

        if (
            deployment_status is not None
            and deployment_status != "Deployed"
        ):
            raise ValueError(
                "CustomObject deploymentStatus "
                "must be Deployed."
            )

        sharing_model = self.config.get(
            "sharingModel"
        )

        if (
            sharing_model is not None
            and sharing_model != "Read"
        ):
            raise ValueError(
                "CustomObject sharingModel "
                "must be Read."
            )

        for key in {
            "pluralLabel",
            "nameFieldLabel",
        }:
            if key in self.config:
                self._require_non_empty_string(
                    self.config[key],
                    (
                        f"CustomObject {key} "
                        "must be a non-empty string."
                    ),
                )

    # =====================================================
    # Custom Field validation
    # =====================================================

    def _validate_custom_field(
        self,
    ) -> None:
        parts = self.fullName.split(
            ".",
            1,
        )

        if (
            len(parts) != 2
            or not parts[0].strip()
            or not parts[1].strip()
        ):
            raise ValueError(
                "CustomField fullName must use "
                "'Object.Field' format."
            )

        # -------------------------------------------------
        # Canonical field type
        # -------------------------------------------------

        field_type = self.config.get(
            "type"
        )

        if not field_type:
            raise ValueError(
                "CustomField config must contain type."
            )

        if (
            not isinstance(field_type, str)
            or field_type
            not in SUPPORTED_FIELD_TYPES
        ):
            raise ValueError(
                "Unsupported Salesforce field type: "
                f"{field_type}"
            )

        # -------------------------------------------------
        # Allowed configuration by field type
        # -------------------------------------------------

        allowed_config = {
            "type",
        } | (
            SalesforceCapabilityRegistry
            .get_field_config_properties(
                field_type
            )
        )

        unsupported = (
            set(
                self.config.keys()
            )
            - allowed_config
        )

        # Preserve a clear error for value arrays on field
        # types that are not single- or multi-select
        # picklists.
        if (
            field_type
            not in {
                "Picklist",
                "MultiselectPicklist",
            }
            and "values"
            in self.config
        ):
            raise ValueError(
                "Only Picklist and "
                "MultiselectPicklist fields may "
                "contain values."
            )

        if unsupported:
            raise ValueError(
                "Unsupported CustomField config: "
                + ", ".join(
                    sorted(
                        unsupported
                    )
                )
            )

        # -------------------------------------------------
        # required must be boolean when supplied
        # -------------------------------------------------

        if "required" in self.config:
            self._validate_boolean(
                self.config["required"],
                (
                    "CustomField required "
                    "must be boolean."
                ),
            )

        # =================================================
        # Text
        # =================================================

        if field_type == "Text":
            if "length" in self.config:
                self._validate_integer_range(
                    value=self.config[
                        "length"
                    ],
                    minimum=1,
                    maximum=255,
                    message=(
                        "Text field length must be "
                        "between 1 and 255."
                    ),
                )

        # =================================================
        # TextArea
        # =================================================

        elif field_type == "TextArea":
            # No additional configuration.
            pass

        # =================================================
        # LongTextArea / Html
        # =================================================

        elif field_type in {
            "LongTextArea",
            "Html",
        }:
            if "length" in self.config:
                self._validate_integer_range(
                    value=self.config[
                        "length"
                    ],
                    minimum=256,
                    maximum=131072,
                    message=(
                        f"{field_type} field length "
                        "must be between "
                        "256 and 131072."
                    ),
                )

            if "visibleLines" in self.config:
                minimum_visible_lines = (
                    11
                    if field_type == "Html"
                    else 2
                )

                self._validate_integer_range(
                    value=self.config[
                        "visibleLines"
                    ],
                    minimum=minimum_visible_lines,
                    maximum=50,
                    message=(
                        f"{field_type} field "
                        "visibleLines must be between "
                        f"{minimum_visible_lines} and 50."
                    ),
                )

        # =================================================
        # EncryptedText
        # =================================================

        elif field_type == "EncryptedText":
            if "length" in self.config:
                self._validate_integer_range(
                    value=self.config[
                        "length"
                    ],
                    minimum=1,
                    maximum=175,
                    message=(
                        "EncryptedText field length "
                        "must be between 1 and 175."
                    ),
                )

            if "maskChar" in self.config:
                mask_char = self.config[
                    "maskChar"
                ]

                if (
                    not isinstance(
                        mask_char,
                        str,
                    )
                    or mask_char
                    not in ENCRYPTED_MASK_CHARS
                ):
                    raise ValueError(
                        "EncryptedText maskChar must "
                        "be 'asterisk' or 'x'."
                    )

            if "maskType" in self.config:
                mask_type = self.config[
                    "maskType"
                ]

                if (
                    not isinstance(
                        mask_type,
                        str,
                    )
                    or mask_type
                    not in ENCRYPTED_MASK_TYPES
                ):
                    raise ValueError(
                        "EncryptedText contains "
                        "unsupported maskType: "
                        f"{mask_type}"
                    )

        # =================================================
        # Email / Phone / Url / Date / DateTime / Time
        # =================================================

        elif field_type in {
            "Email",
            "Phone",
            "Url",
            "Date",
            "DateTime",
            "Time",
        }:
            # type + optional required are sufficient.
            pass

        # =================================================
        # Checkbox
        # =================================================

        elif field_type == "Checkbox":
            if "defaultValue" not in self.config:
                raise ValueError(
                    "Checkbox field must contain "
                    "defaultValue."
                )

            self._validate_boolean(
                self.config[
                    "defaultValue"
                ],
                (
                    "Checkbox defaultValue "
                    "must be boolean."
                ),
            )

        # =================================================
        # Number / Currency / Percent
        # =================================================

        elif field_type in {
            "Number",
            "Currency",
            "Percent",
        }:
            if "precision" not in self.config:
                raise ValueError(
                    f"{field_type} field must contain "
                    "precision."
                )

            if "scale" not in self.config:
                raise ValueError(
                    f"{field_type} field must contain "
                    "scale."
                )

            precision = (
                self._validate_integer_range(
                    value=self.config[
                        "precision"
                    ],
                    minimum=1,
                    maximum=18,
                    message=(
                        f"{field_type} precision must be "
                        "between 1 and 18."
                    ),
                )
            )

            scale = (
                self._validate_integer_range(
                    value=self.config[
                        "scale"
                    ],
                    minimum=0,
                    maximum=17,
                    message=(
                        f"{field_type} scale must be "
                        "between 0 and 17."
                    ),
                )
            )

            if scale > precision:
                raise ValueError(
                    f"{field_type} scale must not "
                    "exceed precision."
                )

        # =================================================
        # Picklist
        # =================================================

        elif field_type == "Picklist":
            values = self.config.get(
                "values"
            )

            self._validate_picklist_values(
                values,
                "Picklist",
            )

        # =================================================
        # MultiselectPicklist
        # =================================================

        elif field_type == "MultiselectPicklist":
            values = self.config.get(
                "values"
            )

            self._validate_picklist_values(
                values,
                "MultiselectPicklist",
            )

            if "visibleLines" not in self.config:
                raise ValueError(
                    "MultiselectPicklist field must "
                    "contain visibleLines."
                )

            self._validate_positive_integer(
                self.config[
                    "visibleLines"
                ],
                (
                    "MultiselectPicklist visibleLines "
                    "must be a positive integer."
                ),
            )

        # =================================================
        # Location / Geolocation
        # =================================================

        elif field_type == "Location":
            if "scale" not in self.config:
                raise ValueError(
                    "Location field must contain scale."
                )

            self._validate_integer_range(
                value=self.config[
                    "scale"
                ],
                minimum=0,
                maximum=15,
                message=(
                    "Location scale must be "
                    "between 0 and 15."
                ),
            )

            if (
                "displayLocationInDecimal"
                in self.config
            ):
                self._validate_boolean(
                    self.config[
                        "displayLocationInDecimal"
                    ],
                    (
                        "Location "
                        "displayLocationInDecimal "
                        "must be boolean."
                    ),
                )

        # =================================================
        # Lookup
        # =================================================

        elif field_type == "Lookup":
            self._validate_relationship_field(
                field_type="Lookup",
                require_delete_constraint=False,
            )

            if "deleteConstraint" in self.config:
                delete_constraint = self.config[
                    "deleteConstraint"
                ]

                if (
                    not isinstance(
                        delete_constraint,
                        str,
                    )
                    or delete_constraint
                    not in LOOKUP_DELETE_CONSTRAINTS
                ):
                    raise ValueError(
                        "Lookup deleteConstraint must be "
                        "SetNull, Restrict, or Cascade."
                    )

        # =================================================
        # MasterDetail
        # =================================================

        elif field_type == "MasterDetail":
            self._validate_relationship_field(
                field_type="MasterDetail",
                require_delete_constraint=False,
            )

            for property_name in {
                "reparentableMasterDetail",
                "writeRequiresMasterRead",
            }:
                if property_name in self.config:
                    self._validate_boolean(
                        self.config[
                            property_name
                        ],
                        (
                            f"MasterDetail {property_name} "
                            "must be boolean."
                        ),
                    )

        # =================================================
        # ExternalLookup
        # =================================================

        elif field_type == "ExternalLookup":
            self._validate_relationship_field(
                field_type="ExternalLookup",
                require_delete_constraint=False,
            )

        # =================================================
        # AutoNumber
        # =================================================

        elif field_type == "AutoNumber":
            display_format = self.config.get(
                "displayFormat"
            )

            self._require_non_empty_string(
                display_format,
                (
                    "AutoNumber field must contain "
                    "displayFormat."
                ),
            )

            if "startingNumber" not in self.config:
                raise ValueError(
                    "AutoNumber field must contain "
                    "startingNumber."
                )

            starting_number = self.config[
                "startingNumber"
            ]

            if isinstance(
                starting_number,
                bool,
            ):
                raise ValueError(
                    "AutoNumber startingNumber must "
                    "be a non-negative integer."
                )

            try:
                parsed_start = int(
                    starting_number
                )

            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "AutoNumber startingNumber must "
                    "be a non-negative integer."
                ) from exc

            if parsed_start < 0:
                raise ValueError(
                    "AutoNumber startingNumber must "
                    "be a non-negative integer."
                )

        # =================================================
        # Formula
        # =================================================

        elif field_type == "Formula":
            formula = self.config.get(
                "formula"
            )

            self._require_non_empty_string(
                formula,
                (
                    "Formula field must contain "
                    "formula."
                ),
            )

            return_type = self.config.get(
                "formulaReturnType"
            )

            self._require_non_empty_string(
                return_type,
                (
                    "Formula field must contain "
                    "formulaReturnType."
                ),
            )

            if (
                return_type
                not in FORMULA_RETURN_TYPES
            ):
                raise ValueError(
                    "Unsupported Formula "
                    "formulaReturnType: "
                    f"{return_type}"
                )

            if return_type in {
                "Number",
                "Currency",
                "Percent",
            }:
                if "precision" not in self.config:
                    raise ValueError(
                        "Numeric Formula field must "
                        "contain precision."
                    )

                if "scale" not in self.config:
                    raise ValueError(
                        "Numeric Formula field must "
                        "contain scale."
                    )

                precision = (
                    self._validate_integer_range(
                        value=self.config[
                            "precision"
                        ],
                        minimum=1,
                        maximum=18,
                        message=(
                            "Formula precision must be "
                            "between 1 and 18."
                        ),
                    )
                )

                scale = (
                    self._validate_integer_range(
                        value=self.config[
                            "scale"
                        ],
                        minimum=0,
                        maximum=17,
                        message=(
                            "Formula scale must be "
                            "between 0 and 17."
                        ),
                    )
                )

                if scale > precision:
                    raise ValueError(
                        "Formula scale must not "
                        "exceed precision."
                    )

            # `length` is accepted because it is currently
            # present in the shared capability schema. The
            # deterministic generator decides whether that
            # property applies to the selected formula
            # return type and never emits unsupported XML.
            if "length" in self.config:
                self._validate_positive_integer(
                    self.config[
                        "length"
                    ],
                    (
                        "Formula length must be "
                        "a positive integer."
                    ),
                )

        # =================================================
        # Roll-Up Summary
        # =================================================

        elif field_type == "Summary":
            foreign_key = self.config.get(
                "summaryForeignKey"
            )

            self._require_non_empty_string(
                foreign_key,
                (
                    "Summary field must contain "
                    "summaryForeignKey."
                ),
            )

            operation = self.config.get(
                "summaryOperation"
            )

            self._require_non_empty_string(
                operation,
                (
                    "Summary field must contain "
                    "summaryOperation."
                ),
            )

            if (
                operation
                not in SUMMARY_OPERATIONS
            ):
                raise ValueError(
                    "Summary summaryOperation must be "
                    "Count, Min, Max, or Sum."
                )

            if operation == "Count":
                if (
                    "summarizedField"
                    in self.config
                    and self.config[
                        "summarizedField"
                    ] is not None
                ):
                    raise ValueError(
                        "Summary Count must not contain "
                        "summarizedField."
                    )

            else:
                summarized_field = self.config.get(
                    "summarizedField"
                )

                self._require_non_empty_string(
                    summarized_field,
                    (
                        f"Summary {operation} must contain "
                        "summarizedField."
                    ),
                )

    # -----------------------------------------------------
    # Relationship field helper
    # -----------------------------------------------------

    def _validate_relationship_field(
        self,
        field_type: str,
        require_delete_constraint: bool,
    ) -> None:
        reference_to = self.config.get(
            "referenceTo"
        )

        self._require_non_empty_string(
            reference_to,
            (
                f"{field_type} field must contain "
                "referenceTo."
            ),
        )

        relationship_name = self.config.get(
            "relationshipName"
        )

        self._require_non_empty_string(
            relationship_name,
            (
                f"{field_type} field must contain "
                "relationshipName."
            ),
        )

        if require_delete_constraint:
            delete_constraint = self.config.get(
                "deleteConstraint"
            )

            if (
                not isinstance(
                    delete_constraint,
                    str,
                )
                or delete_constraint
                not in LOOKUP_DELETE_CONSTRAINTS
            ):
                raise ValueError(
                    f"{field_type} field must contain "
                    "a valid deleteConstraint."
                )

    # =====================================================
    # Validation Rule validation
    # =====================================================

    def _validate_validation_rule(
        self,
    ) -> None:
        parts = self.fullName.split(
            ".",
            1,
        )

        if (
            len(parts) != 2
            or not parts[0].strip()
            or not parts[1].strip()
        ):
            raise ValueError(
                "ValidationRule fullName must use "
                "'Object.RuleName' format."
            )

        allowed_config = {
            "active",
            "errorConditionFormula",
            "errorMessage",
            "errorDisplayField",
        }

        unsupported = (
            set(
                self.config.keys()
            )
            - allowed_config
        )

        if unsupported:
            raise ValueError(
                "Unsupported ValidationRule config: "
                + ", ".join(
                    sorted(
                        unsupported
                    )
                )
            )

        if "active" not in self.config:
            raise ValueError(
                "ValidationRule config must contain active."
            )

        self._validate_boolean(
            self.config[
                "active"
            ],
            (
                "ValidationRule active "
                "must be boolean."
            ),
        )

        formula = self.config.get(
            "errorConditionFormula"
        )

        self._require_non_empty_string(
            formula,
            (
                "ValidationRule config must contain "
                "errorConditionFormula."
            ),
        )

        validate_formula_regex_escaping(formula)

        error_message = self.config.get(
            "errorMessage"
        )

        message = self._require_non_empty_string(
            error_message,
            (
                "ValidationRule config must contain "
                "errorMessage."
            ),
        )

        if len(message) > 255:
            raise ValueError(
                "ValidationRule errorMessage must not "
                "exceed 255 characters."
            )

        if "errorDisplayField" in self.config:
            self._require_non_empty_string(
                self.config[
                    "errorDisplayField"
                ],
                (
                    "ValidationRule errorDisplayField "
                    "must be a non-empty string."
                ),
            )


# =========================================================
# Metadata Specification
# =========================================================

class MetadataSpecification(BaseModel):
    """
    Complete metadata specification generated from
    an approved implementation plan.
    """

    planId: str = Field(
        min_length=1
    )

    metadata: list[
        MetadataItem
    ] = Field(
        default_factory=list
    )

    validationIssues: list[
        MetadataValidationIssue
    ] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_specification(
        self,
    ):
        item_ids = [
            item.itemId
            for item in self.metadata
        ]

        if len(
            item_ids
        ) != len(
            set(
                item_ids
            )
        ):
            raise ValueError(
                "Duplicate metadata itemId detected."
            )

        # Prevent duplicate output components.
        component_keys = [
            (
                item.metadataType,
                item.fullName,
            )
            for item in self.metadata
        ]

        if len(
            component_keys
        ) != len(
            set(
                component_keys
            )
        ):
            raise ValueError(
                "Duplicate metadata component detected."
            )

        return self


# =========================================================
# Validation Result
# =========================================================

class MetadataSpecValidationResult(BaseModel):
    """
    Result returned when validating raw AI output.
    """

    valid: bool

    errors: list[str] = Field(
        default_factory=list
    )


# =========================================================
# Public Validator
# =========================================================

def validate_metadata_spec(
    data: dict,
) -> MetadataSpecValidationResult:
    """
    Validate raw metadata specification data.

    This function does not generate files and does
    not deploy anything.
    """

    if not isinstance(
        data,
        dict,
    ):
        return MetadataSpecValidationResult(
            valid=False,
            errors=[
                "Metadata specification must be "
                "a dictionary."
            ],
        )

    try:
        MetadataSpecification.model_validate(
            data
        )

        return MetadataSpecValidationResult(
            valid=True,
            errors=[],
        )

    except Exception as exc:
        return MetadataSpecValidationResult(
            valid=False,
            errors=[
                str(exc)
            ],
        )


def validate_formula_regex_escaping(formula: str) -> None:
    """Catch the known invalid single-backslash-plus string escape.

    This is a focused lexical check, not a Salesforce formula compiler.
    Preserve correctly doubled backslashes and ignore block comments.
    """
    quoted = False
    index = 0
    while index < len(formula):
        if not quoted and formula.startswith('/*', index):
            end = formula.find('*/', index + 2)
            if end < 0:
                return  # Salesforce compilation handles malformed comments.
            index = end + 2
            continue
        char = formula[index]
        if char == '"':
            quoted = not quoted
        elif quoted and char == chr(92):
            if index + 1 < len(formula) and formula[index + 1] == '+':
                raise ValueError(
                    'Invalid single-backslash-plus escape in errorConditionFormula '
                    f'at character {index + 1}. Use [+] for a literal plus in REGEX, '
                    'or correctly double the formula backslash before JSON serialization. '
                    'Correct the plan before approval; XML CDATA does not fix formula escapes.'
                )
            index += 1  # Skip escaped character, including another backslash.
        index += 1
