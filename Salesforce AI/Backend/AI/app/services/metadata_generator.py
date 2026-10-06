from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)
from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
)
from Backend.AI.app.services.field_type_registry import (
    SalesforceFieldTypeRegistry,
)


SALESFORCE_METADATA_NS = (
    "http://soap.sforce.com/2006/04/metadata"
)


class SalesforceMetadataGenerator:
    """
    Generates Salesforce DX source-format metadata files.

    Supported CREATE metadata:

    - CustomObject
    - CustomField
    - ValidationRule

    Supported CustomField families:

    - AutoNumber
    - Formula
    - Summary
    - Lookup
    - MasterDetail
    - ExternalLookup
    - Checkbox
    - Currency
    - Date
    - DateTime
    - Email
    - Location
    - Number
    - Percent
    - Phone
    - Picklist
    - MultiselectPicklist
    - Text
    - TextArea
    - LongTextArea
    - Html
    - EncryptedText
    - Time
    - Url

    This service creates local files only.
    It does not execute Salesforce CLI commands and does not deploy.
    """

    def __init__(
        self,
        project_root: str = ".",
    ):
        self.project_root = Path(
            project_root
        )

        self.metadata_root = (
            self.project_root
            / "force-app"
            / "main"
            / "default"
        )

    # =====================================================
    # Implementation Plan Validation
    # =====================================================

    def validate_plan(
        self,
        plan: ImplementationPlan,
    ) -> None:
        """
        Only APPROVED plans can generate metadata.
        """

        if plan.status != "APPROVED":
            raise ValueError(
                "Only APPROVED plans can generate metadata."
            )

    # =====================================================
    # Existing ImplementationPlan Generation
    # =====================================================

    def generate(
        self,
        plan: ImplementationPlan,
    ) -> list[str]:
        """
        Generate Salesforce DX files directly from an
        approved ImplementationPlan.

        This path remains for backward compatibility.
        The preferred AI path is MetadataSpecification.
        """

        self.validate_plan(
            plan
        )

        generated_files: list[str] = []

        for item in plan.items:

            if item.action != "CREATE":
                continue

            file_path = (
                self._generate_item(
                    item
                )
            )

            if file_path is not None:
                generated_files.append(
                    str(file_path)
                )

        return generated_files

    # =====================================================
    # MetadataSpecification Generation
    # =====================================================

    def generate_from_specification(
        self,
        specification: MetadataSpecification,
    ) -> list[str]:
        """
        Generate Salesforce DX files from a validated
        MetadataSpecification.
        """

        if specification.validationIssues:
            raise ValueError(
                "Metadata specification contains "
                "validation issues."
            )

        generated_files: list[str] = []

        for item in specification.metadata:

            if item.action != "CREATE":
                continue

            file_path = (
                self._generate_item(
                    item
                )
            )

            if file_path is not None:
                generated_files.append(
                    str(file_path)
                )

        return generated_files

    # =====================================================
    # Metadata Item Router
    # =====================================================

    def _generate_item(
        self,
        item,
    ) -> Path | None:

        if item.metadataType == "CustomObject":
            return self._generate_custom_object(
                item
            )

        if item.metadataType == "CustomField":
            return self._generate_custom_field(
                item
            )

        if item.metadataType == "ValidationRule":
            return self._generate_validation_rule(
                item
            )

        raise ValueError(
            "Unsupported Salesforce metadata type: "
            f"{item.metadataType}"
        )

    # =====================================================
    # Custom Object Generator
    # =====================================================

    def _generate_custom_object(
        self,
        item,
    ) -> Path:
        """
        Generate a Salesforce CustomObject source file.
        """

        objects_dir = (
            self.metadata_root
            / "objects"
            / item.fullName
        )

        objects_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path = (
            objects_dir
            / f"{item.fullName}.object-meta.xml"
        )

        label = (
            item.label
            or item.fullName
        )

        config = (
            item.config
            or {}
        )

        plural_label = config.get(
            "pluralLabel",
            f"{label}s",
        )

        name_field_label = config.get(
            "nameFieldLabel",
            f"{label} Name",
        )

        name_field_type = config.get(
            "nameFieldType",
            "Text",
        )

        deployment_status = config.get(
            "deploymentStatus",
            "Deployed",
        )

        sharing_model = config.get(
            "sharingModel",
            "Read",
        )

        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="{SALESFORCE_METADATA_NS}">
    <label>{escape(str(label))}</label>
    <pluralLabel>{escape(str(plural_label))}</pluralLabel>
    <nameField>
        <label>{escape(str(name_field_label))}</label>
        <type>{escape(str(name_field_type))}</type>
    </nameField>
    <deploymentStatus>{escape(str(deployment_status))}</deploymentStatus>
    <sharingModel>{escape(str(sharing_model))}</sharingModel>
</CustomObject>
"""

        file_path.write_text(
            content,
            encoding="utf-8",
        )

        return file_path

    # =====================================================
    # Custom Field Generator
    # =====================================================

    def _generate_custom_field(
        self,
        item,
    ) -> Path:
        """
        Generate a Salesforce CustomField source file.
        """

        parts = item.fullName.split(
            ".",
            1,
        )

        if (
            len(parts) != 2
            or not parts[0]
            or not parts[1]
        ):
            raise ValueError(
                "CustomField fullName must use "
                "'Object.Field' format."
            )

        object_name = parts[0]
        field_name = parts[1]

        fields_dir = (
            self.metadata_root
            / "objects"
            / object_name
            / "fields"
        )

        fields_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path = (
            fields_dir
            / f"{field_name}.field-meta.xml"
        )

        config = (
            item.config
            or {}
        )

        field_type = (
            config.get("fieldType")
            or config.get("type")
        )

        if not field_type:
            raise ValueError(
                f"CustomField '{item.fullName}' "
                "must contain fieldType or type."
            )

        required = config.get(
            "required",
            False,
        )

        content = self._build_field_xml(
            item=item,
            field_type=field_type,
            required=required,
        )

        file_path.write_text(
            content,
            encoding="utf-8",
        )

        return file_path

    # =====================================================
    # Validation Rule Generator
    # =====================================================

    def _generate_validation_rule(
        self,
        item,
    ) -> Path:
        """
        Generate a Salesforce ValidationRule source file.

        Expected fullName:
            ObjectApiName.RuleApiName
        """

        parts = item.fullName.split(
            ".",
            1,
        )

        if (
            len(parts) != 2
            or not parts[0]
            or not parts[1]
        ):
            raise ValueError(
                "ValidationRule fullName must use "
                "'Object.RuleName' format."
            )

        object_name = parts[0]
        rule_name = parts[1]

        rules_dir = (
            self.metadata_root
            / "objects"
            / object_name
            / "validationRules"
        )

        rules_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path = (
            rules_dir
            / (
                f"{rule_name}"
                ".validationRule-meta.xml"
            )
        )

        config = (
            item.config
            or {}
        )

        if "active" not in config:
            raise ValueError(
                f"ValidationRule '{item.fullName}' "
                "must contain active."
            )

        active = config[
            "active"
        ]

        if not isinstance(
            active,
            bool,
        ):
            raise ValueError(
                f"ValidationRule '{item.fullName}' "
                "active must be boolean."
            )

        formula = self._require_text(
            config.get(
                "errorConditionFormula"
            ),
            (
                f"ValidationRule '{item.fullName}' "
                "must contain errorConditionFormula."
            ),
        )

        error_message = self._require_text(
            config.get(
                "errorMessage"
            ),
            (
                f"ValidationRule '{item.fullName}' "
                "must contain errorMessage."
            ),
        )

        if len(error_message) > 255:
            raise ValueError(
                f"ValidationRule '{item.fullName}' "
                "errorMessage must not exceed "
                "255 characters."
            )

        description_xml = ""

        if item.description:
            description_xml = (
                "\n    <description>"
                + escape(
                    str(
                        item.description
                    )
                )
                + "</description>"
            )

        error_display_xml = ""

        if config.get(
            "errorDisplayField"
        ):
            error_display_xml = (
                "\n    <errorDisplayField>"
                + escape(
                    str(
                        config[
                            "errorDisplayField"
                        ]
                    )
                )
                + "</errorDisplayField>"
            )

        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ValidationRule xmlns="{SALESFORCE_METADATA_NS}">
    <fullName>{escape(rule_name)}</fullName>
    <active>{str(active).lower()}</active>{description_xml}
    <errorConditionFormula>{self._cdata(formula)}</errorConditionFormula>{error_display_xml}
    <errorMessage>{escape(error_message)}</errorMessage>
</ValidationRule>
"""

        file_path.write_text(
            content,
            encoding="utf-8",
        )

        return file_path

    # =====================================================
    # Field XML Builder
    # =====================================================

    def _build_field_xml(
        self,
        item,
        field_type: str,
        required: bool,
    ) -> str:
        """
        Build Salesforce CustomField XML.
        """

        label = (
            item.label
            or item.fullName
        )

        field_name = item.fullName.split(
            ".",
            1,
        )[1]

        config = (
            item.config
            or {}
        )

        field_type = (
            SalesforceFieldTypeRegistry
            .normalize(
                field_type
            )
        )

        if not isinstance(
            required,
            bool,
        ):
            raise ValueError(
                f"CustomField '{field_name}' "
                "required must be boolean."
            )

        # ==================================================
        # Text
        # ==================================================

        if field_type == "Text":

            length = self._integer_in_range(
                config.get(
                    "length",
                    255,
                ),
                minimum=1,
                maximum=255,
                message=(
                    f"Text field '{field_name}' length "
                    "must be between 1 and 255."
                ),
            )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <length>{length}</length>\n"
                    f"    <required>{str(required).lower()}</required>\n"
                    "    <type>Text</type>"
                ),
            )

        # ==================================================
        # Text Area
        # ==================================================

        if field_type == "TextArea":

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <required>{str(required).lower()}</required>\n"
                    "    <type>TextArea</type>"
                ),
            )

        # ==================================================
        # Long Text Area / Rich Text Area
        # ==================================================

        if field_type in {
            "LongTextArea",
            "Html",
        }:

            length = self._integer_in_range(
                config.get(
                    "length",
                    32768,
                ),
                minimum=256,
                maximum=131072,
                message=(
                    f"{field_type} field '{field_name}' "
                    "length must be between "
                    "256 and 131072."
                ),
            )

            default_visible_lines = (
                25
                if field_type == "Html"
                else 6
            )

            minimum_visible_lines = (
                11
                if field_type == "Html"
                else 2
            )

            visible_lines = (
                self._integer_in_range(
                    config.get(
                        "visibleLines",
                        default_visible_lines,
                    ),
                    minimum=minimum_visible_lines,
                    maximum=50,
                    message=(
                        f"{field_type} field "
                        f"'{field_name}' visibleLines "
                        "must be between "
                        f"{minimum_visible_lines} and 50."
                    ),
                )
            )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <length>{length}</length>\n"
                    f"    <required>{str(required).lower()}</required>\n"
                    f"    <type>{field_type}</type>\n"
                    f"    <visibleLines>{visible_lines}</visibleLines>"
                ),
            )

        # ==================================================
        # Encrypted Text
        # ==================================================

        if field_type == "EncryptedText":

            length = self._integer_in_range(
                config.get(
                    "length",
                    175,
                ),
                minimum=1,
                maximum=175,
                message=(
                    f"EncryptedText field '{field_name}' "
                    "length must be between 1 and 175."
                ),
            )

            raw_mask_char = str(
                config.get(
                    "maskChar",
                    "asterisk",
                )
            ).strip()

            mask_char_aliases = {
                "*": "asterisk",
                "asterisk": "asterisk",
                "x": "x",
                "X": "x",
            }

            mask_char = (
                mask_char_aliases.get(
                    raw_mask_char
                )
            )

            if mask_char is None:
                raise ValueError(
                    f"EncryptedText field '{field_name}' "
                    "maskChar must be "
                    "'asterisk' or 'x'."
                )

            mask_type = str(
                config.get(
                    "maskType",
                    "all",
                )
            ).strip()

            supported_mask_types = {
                "all",
                "creditCard",
                "ssn",
                "lastFour",
                "sin",
                "nino",
            }

            if (
                mask_type
                not in supported_mask_types
            ):
                raise ValueError(
                    f"EncryptedText field '{field_name}' "
                    "contains unsupported maskType: "
                    f"{mask_type}"
                )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <length>{length}</length>\n"
                    f"    <maskChar>{mask_char}</maskChar>\n"
                    f"    <maskType>{escape(mask_type)}</maskType>\n"
                    f"    <required>{str(required).lower()}</required>\n"
                    "    <type>EncryptedText</type>"
                ),
            )

        # ==================================================
        # Email / Phone / Url / Date / DateTime / Time
        # ==================================================

        if field_type in {
            "Email",
            "Phone",
            "Url",
            "Date",
            "DateTime",
            "Time",
        }:

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <required>{str(required).lower()}</required>\n"
                    f"    <type>{field_type}</type>"
                ),
            )

        # ==================================================
        # Checkbox
        # ==================================================

        if field_type == "Checkbox":

            default_value = config.get(
                "defaultValue",
                False,
            )

            if not isinstance(
                default_value,
                bool,
            ):
                raise ValueError(
                    f"Checkbox field '{field_name}' "
                    "defaultValue must be boolean."
                )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <defaultValue>{str(default_value).lower()}</defaultValue>\n"
                    f"    <label>{escape(str(label))}</label>\n"
                    "    <type>Checkbox</type>"
                ),
            )

        # ==================================================
        # Number / Currency / Percent
        # ==================================================

        if field_type in {
            "Number",
            "Currency",
            "Percent",
        }:

            if "precision" not in config:
                raise ValueError(
                    f"{field_type} field '{field_name}' "
                    "must contain precision."
                )

            if "scale" not in config:
                raise ValueError(
                    f"{field_type} field '{field_name}' "
                    "must contain scale."
                )

            precision = self._integer_in_range(
                config[
                    "precision"
                ],
                minimum=1,
                maximum=18,
                message=(
                    f"{field_type} field '{field_name}' "
                    "precision must be between 1 and 18."
                ),
            )

            scale = self._integer_in_range(
                config[
                    "scale"
                ],
                minimum=0,
                maximum=17,
                message=(
                    f"{field_type} field '{field_name}' "
                    "scale must be between 0 and 17."
                ),
            )

            if scale > precision:
                raise ValueError(
                    f"{field_type} field '{field_name}' "
                    "scale must not exceed precision."
                )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <precision>{precision}</precision>\n"
                    f"    <required>{str(required).lower()}</required>\n"
                    f"    <scale>{scale}</scale>\n"
                    f"    <type>{field_type}</type>"
                ),
            )

        # ==================================================
        # Picklist / MultiselectPicklist
        # ==================================================

        if field_type in {
            "Picklist",
            "MultiselectPicklist",
        }:

            values = (
                config.get(
                    "picklistValues"
                )
                or config.get(
                    "values"
                )
                or []
            )

            self._validate_values(
                field_name=field_name,
                field_type=field_type,
                values=values,
            )

            value_set_xml = (
                self._build_value_set_xml(
                    values
                )
            )

            if field_type == "Picklist":

                return self._field_document(
                    field_name=field_name,
                    body=(
                        f"    <label>{escape(str(label))}</label>\n"
                        f"    <required>{str(required).lower()}</required>\n"
                        "    <type>Picklist</type>\n"
                        f"{value_set_xml}"
                    ),
                )

            if "visibleLines" not in config:
                raise ValueError(
                    f"MultiselectPicklist field "
                    f"'{field_name}' must contain "
                    "visibleLines."
                )

            visible_lines = (
                self._positive_integer(
                    config[
                        "visibleLines"
                    ],
                    (
                        f"MultiselectPicklist field "
                        f"'{field_name}' visibleLines "
                        "must be a positive integer."
                    ),
                )
            )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    "    <type>MultiselectPicklist</type>\n"
                    f"{value_set_xml}\n"
                    f"    <visibleLines>{visible_lines}</visibleLines>"
                ),
            )

        # ==================================================
        # Location / Geolocation
        # ==================================================

        if field_type == "Location":

            if "scale" not in config:
                raise ValueError(
                    f"Location field '{field_name}' "
                    "must contain scale."
                )

            scale = self._integer_in_range(
                config[
                    "scale"
                ],
                minimum=0,
                maximum=15,
                message=(
                    f"Location field '{field_name}' "
                    "scale must be between 0 and 15."
                ),
            )

            display_decimal = config.get(
                "displayLocationInDecimal",
                True,
            )

            if not isinstance(
                display_decimal,
                bool,
            ):
                raise ValueError(
                    f"Location field '{field_name}' "
                    "displayLocationInDecimal "
                    "must be boolean."
                )

            return self._field_document(
                field_name=field_name,
                body=(
                    "    <displayLocationInDecimal>"
                    f"{str(display_decimal).lower()}"
                    "</displayLocationInDecimal>\n"
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <required>{str(required).lower()}</required>\n"
                    f"    <scale>{scale}</scale>\n"
                    "    <type>Location</type>"
                ),
            )

        # ==================================================
        # Lookup / ExternalLookup
        # ==================================================

        if field_type in {
            "Lookup",
            "ExternalLookup",
        }:

            reference_to = self._require_text(
                config.get(
                    "referenceTo"
                ),
                (
                    f"{field_type} field '{field_name}' "
                    "must contain referenceTo."
                ),
            )

            relationship_name = self._require_text(
                config.get(
                    "relationshipName"
                ),
                (
                    f"{field_type} field '{field_name}' "
                    "must contain relationshipName."
                ),
            )

            delete_constraint_xml = ""

            if (
                field_type == "Lookup"
                and config.get(
                    "deleteConstraint"
                )
            ):
                constraint = str(
                    config[
                        "deleteConstraint"
                    ]
                ).strip()

                if constraint not in {
                    "SetNull",
                    "Restrict",
                    "Cascade",
                }:
                    raise ValueError(
                        f"Lookup field '{field_name}' "
                        "deleteConstraint must be "
                        "SetNull, Restrict, or Cascade."
                    )

                delete_constraint_xml = (
                    "    <deleteConstraint>"
                    f"{constraint}"
                    "</deleteConstraint>\n"
                )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"{delete_constraint_xml}"
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <referenceTo>{escape(reference_to)}</referenceTo>\n"
                    f"    <relationshipName>{escape(relationship_name)}</relationshipName>\n"
                    f"    <required>{str(required).lower()}</required>\n"
                    f"    <type>{field_type}</type>"
                ),
            )

        # ==================================================
        # MasterDetail
        # ==================================================

        if field_type == "MasterDetail":

            reference_to = self._require_text(
                config.get(
                    "referenceTo"
                ),
                (
                    f"MasterDetail field '{field_name}' "
                    "must contain referenceTo."
                ),
            )

            relationship_name = self._require_text(
                config.get(
                    "relationshipName"
                ),
                (
                    f"MasterDetail field '{field_name}' "
                    "must contain relationshipName."
                ),
            )

            reparentable = config.get(
                "reparentableMasterDetail",
                False,
            )

            write_requires_master_read = (
                config.get(
                    "writeRequiresMasterRead",
                    False,
                )
            )

            if not isinstance(
                reparentable,
                bool,
            ):
                raise ValueError(
                    f"MasterDetail field '{field_name}' "
                    "reparentableMasterDetail "
                    "must be boolean."
                )

            if not isinstance(
                write_requires_master_read,
                bool,
            ):
                raise ValueError(
                    f"MasterDetail field '{field_name}' "
                    "writeRequiresMasterRead "
                    "must be boolean."
                )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <referenceTo>{escape(reference_to)}</referenceTo>\n"
                    f"    <relationshipName>{escape(relationship_name)}</relationshipName>\n"
                    "    <reparentableMasterDetail>"
                    f"{str(reparentable).lower()}"
                    "</reparentableMasterDetail>\n"
                    "    <type>MasterDetail</type>\n"
                    "    <writeRequiresMasterRead>"
                    f"{str(write_requires_master_read).lower()}"
                    "</writeRequiresMasterRead>"
                ),
            )

        # ==================================================
        # AutoNumber
        # ==================================================

        if field_type == "AutoNumber":

            display_format = self._require_text(
                config.get(
                    "displayFormat"
                ),
                (
                    f"AutoNumber field '{field_name}' "
                    "must contain displayFormat."
                ),
            )

            if "startingNumber" not in config:
                raise ValueError(
                    f"AutoNumber field '{field_name}' "
                    "must contain startingNumber."
                )

            starting_number = (
                self._non_negative_integer(
                    config[
                        "startingNumber"
                    ],
                    (
                        f"AutoNumber field '{field_name}' "
                        "startingNumber must be a "
                        "non-negative integer."
                    ),
                )
            )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <displayFormat>{escape(display_format)}</displayFormat>\n"
                    f"    <label>{escape(str(label))}</label>\n"
                    f"    <startingNumber>{starting_number}</startingNumber>\n"
                    "    <type>AutoNumber</type>"
                ),
            )

        # ==================================================
        # Formula
        # ==================================================

        if field_type == "Formula":

            formula = self._require_text(
                config.get(
                    "formula"
                ),
                (
                    f"Formula field '{field_name}' "
                    "must contain formula."
                ),
            )

            return_type = self._require_text(
                config.get(
                    "formulaReturnType"
                ),
                (
                    f"Formula field '{field_name}' "
                    "must contain formulaReturnType."
                ),
            )

            supported_return_types = {
                "Checkbox",
                "Currency",
                "Date",
                "DateTime",
                "Number",
                "Percent",
                "Text",
                "Time",
            }

            if (
                return_type
                not in supported_return_types
            ):
                raise ValueError(
                    f"Formula field '{field_name}' "
                    "contains unsupported "
                    "formulaReturnType: "
                    f"{return_type}"
                )

            formula_treat_blanks_as = (
                "BlankAsZero"
                if return_type
                in {
                    "Number",
                    "Currency",
                    "Percent",
                }
                else "BlankAsBlank"
            )

            numeric_xml = ""

            if return_type in {
                "Number",
                "Currency",
                "Percent",
            }:

                if "precision" not in config:
                    raise ValueError(
                        f"Formula field '{field_name}' "
                        "must contain precision for "
                        f"{return_type}."
                    )

                if "scale" not in config:
                    raise ValueError(
                        f"Formula field '{field_name}' "
                        "must contain scale for "
                        f"{return_type}."
                    )

                precision = (
                    self._integer_in_range(
                        config[
                            "precision"
                        ],
                        minimum=1,
                        maximum=18,
                        message=(
                            f"Formula field '{field_name}' "
                            "precision must be between "
                            "1 and 18."
                        ),
                    )
                )

                scale = (
                    self._integer_in_range(
                        config[
                            "scale"
                        ],
                        minimum=0,
                        maximum=17,
                        message=(
                            f"Formula field '{field_name}' "
                            "scale must be between "
                            "0 and 17."
                        ),
                    )
                )

                if scale > precision:
                    raise ValueError(
                        f"Formula field '{field_name}' "
                        "scale must not exceed precision."
                    )

                numeric_xml = (
                    f"    <precision>{precision}</precision>\n"
                    f"    <scale>{scale}</scale>\n"
                )

            # Salesforce formula fields do not use
            # <type>Formula</type>. The type is the formula
            # result type.
            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <formula>{self._cdata(formula)}</formula>\n"
                    "    <formulaTreatBlanksAs>"
                    f"{formula_treat_blanks_as}"
                    "</formulaTreatBlanksAs>\n"
                    f"    <label>{escape(str(label))}</label>\n"
                    f"{numeric_xml}"
                    f"    <type>{return_type}</type>"
                ),
            )

        # ==================================================
        # Roll-Up Summary
        # ==================================================

        if field_type == "Summary":

            foreign_key = self._require_text(
                config.get(
                    "summaryForeignKey"
                ),
                (
                    f"Summary field '{field_name}' "
                    "must contain summaryForeignKey."
                ),
            )

            raw_operation = self._require_text(
                config.get(
                    "summaryOperation"
                ),
                (
                    f"Summary field '{field_name}' "
                    "must contain summaryOperation."
                ),
            )

            operation_aliases = {
                "count": "count",
                "min": "min",
                "max": "max",
                "sum": "sum",
            }

            operation = (
                operation_aliases.get(
                    raw_operation.lower()
                )
            )

            if operation is None:
                raise ValueError(
                    f"Summary field '{field_name}' "
                    "summaryOperation must be "
                    "Count, Min, Max, or Sum."
                )

            summarized_xml = ""

            if operation != "count":

                summarized_field = (
                    self._require_text(
                        config.get(
                            "summarizedField"
                        ),
                        (
                            f"Summary field '{field_name}' "
                            f"operation '{raw_operation}' "
                            "must contain summarizedField."
                        ),
                    )
                )

                summarized_xml = (
                    "    <summarizedField>"
                    f"{escape(summarized_field)}"
                    "</summarizedField>\n"
                )

            return self._field_document(
                field_name=field_name,
                body=(
                    f"    <label>{escape(str(label))}</label>\n"
                    f"{summarized_xml}"
                    "    <summaryForeignKey>"
                    f"{escape(foreign_key)}"
                    "</summaryForeignKey>\n"
                    "    <summaryOperation>"
                    f"{operation}"
                    "</summaryOperation>\n"
                    "    <type>Summary</type>"
                ),
            )

        raise ValueError(
            "Unsupported Salesforce field type: "
            f"{field_type}"
        )

    # =====================================================
    # XML Helpers
    # =====================================================

    @staticmethod
    def _field_document(
        field_name: str,
        body: str,
    ) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="{SALESFORCE_METADATA_NS}">
    <fullName>{escape(field_name)}</fullName>
{body}
</CustomField>
"""

    @staticmethod
    def _build_value_set_xml(
        values: list,
    ) -> str:

        value_xml = ""

        for value in values:
            escaped_value = escape(
                str(value).strip()
            )

            value_xml += f"""
            <value>
                <fullName>{escaped_value}</fullName>
                <default>false</default>
                <label>{escaped_value}</label>
            </value>"""

        return (
            "    <valueSet>\n"
            "        <valueSetDefinition>\n"
            "            <sorted>false</sorted>"
            f"{value_xml}\n"
            "        </valueSetDefinition>\n"
            "    </valueSet>"
        )

    @staticmethod
    def _validate_values(
        field_name: str,
        field_type: str,
        values,
    ) -> None:

        if (
            not isinstance(
                values,
                list,
            )
            or not values
        ):
            raise ValueError(
                f"{field_type} field '{field_name}' "
                "must contain at least one value."
            )

        normalized: list[str] = []

        for value in values:
            if (
                not isinstance(
                    value,
                    str,
                )
                or not value.strip()
            ):
                raise ValueError(
                    f"{field_type} field "
                    f"'{field_name}' values must be "
                    "non-empty strings."
                )

            normalized.append(
                value.strip()
            )

        if len(
            normalized
        ) != len(
            set(
                normalized
            )
        ):
            raise ValueError(
                f"{field_type} field '{field_name}' "
                "values must be unique."
            )

    @staticmethod
    def _require_text(
        value,
        message: str,
    ) -> str:

        if (
            not isinstance(
                value,
                str,
            )
            or not value.strip()
        ):
            raise ValueError(
                message
            )

        return value.strip()

    @staticmethod
    def _integer_in_range(
        value,
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
            parsed = int(
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
            <= parsed
            <= maximum
        ):
            raise ValueError(
                message
            )

        return parsed

    @staticmethod
    def _positive_integer(
        value,
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
            parsed = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                message
            ) from exc

        if parsed < 1:
            raise ValueError(
                message
            )

        return parsed

    @staticmethod
    def _non_negative_integer(
        value,
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
            parsed = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                message
            ) from exc

        if parsed < 0:
            raise ValueError(
                message
            )

        return parsed

    @staticmethod
    def _cdata(
        value: str,
    ) -> str:
        """
        Safely wrap formulas in CDATA.

        The literal ']]>' sequence is split across two
        adjacent CDATA sections.
        """

        safe_value = value.replace(
            "]]>",
            "]]]]><![CDATA[>",
        )

        return (
            "<![CDATA["
            + safe_value
            + "]]>"
        )
