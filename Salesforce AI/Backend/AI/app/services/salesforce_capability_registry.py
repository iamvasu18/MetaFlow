from __future__ import annotations


class SalesforceCapabilityRegistry:
    """
    Central registry for Salesforce development capabilities.

    This registry defines:

    1. Canonical Salesforce field types
    2. Natural-language aliases
    3. Configuration properties expected for each field type
    4. Salesforce metadata component types
    5. Future development component families

    Important:
    The registry describes application capabilities.

    Validators and generators are still responsible for enforcing
    the actual configuration rules for each component.
    """

    # =====================================================
    # Field Type Aliases
    # =====================================================

    FIELD_TYPE_ALIASES = {
        # -------------------------------------------------
        # Text family
        # -------------------------------------------------
        "text": "Text",
        "string": "Text",

        "text area": "TextArea",
        "textarea": "TextArea",

        "long text": "LongTextArea",
        "long text area": "LongTextArea",
        "text area long": "LongTextArea",
        "text area (long)": "LongTextArea",
        "longtextarea": "LongTextArea",

        "rich text": "Html",
        "rich text area": "Html",
        "text area rich": "Html",
        "text area (rich)": "Html",
        "html": "Html",

        "encrypted text": "EncryptedText",
        "text encrypted": "EncryptedText",
        "text (encrypted)": "EncryptedText",
        "encryptedtext": "EncryptedText",

        # -------------------------------------------------
        # Numeric
        # -------------------------------------------------
        "number": "Number",
        "integer": "Number",
        "decimal": "Number",

        "currency": "Currency",
        "money": "Currency",

        "percent": "Percent",
        "percentage": "Percent",

        # -------------------------------------------------
        # Boolean
        # -------------------------------------------------
        "checkbox": "Checkbox",
        "boolean": "Checkbox",
        "bool": "Checkbox",

        # -------------------------------------------------
        # Date / Time
        # -------------------------------------------------
        "date": "Date",

        "datetime": "DateTime",
        "date time": "DateTime",
        "date/time": "DateTime",

        "time": "Time",

        # -------------------------------------------------
        # Contact / URL
        # -------------------------------------------------
        "email": "Email",

        "phone": "Phone",

        "url": "Url",
        "website": "Url",

        # -------------------------------------------------
        # Picklists
        # -------------------------------------------------
        "picklist": "Picklist",
        "single select picklist": "Picklist",

        "multi select picklist": "MultiselectPicklist",
        "multi-select picklist": "MultiselectPicklist",
        "picklist multi-select": "MultiselectPicklist",
        "picklist (multi-select)": "MultiselectPicklist",
        "multiselect picklist": "MultiselectPicklist",
        "multiselectpicklist": "MultiselectPicklist",

        # -------------------------------------------------
        # Relationships
        # -------------------------------------------------
        "lookup": "Lookup",
        "lookup relationship": "Lookup",

        "master detail": "MasterDetail",
        "master-detail": "MasterDetail",
        "master detail relationship": "MasterDetail",
        "master-detail relationship": "MasterDetail",

        "external lookup": "ExternalLookup",
        "external lookup relationship": "ExternalLookup",

        # -------------------------------------------------
        # Special field types
        # -------------------------------------------------
        "auto number": "AutoNumber",
        "autonumber": "AutoNumber",

        "formula": "Formula",
        "formula field": "Formula",

        "roll up summary": "Summary",
        "roll-up summary": "Summary",
        "rollup summary": "Summary",
        "summary": "Summary",

        # -------------------------------------------------
        # Location
        # -------------------------------------------------
        "location": "Location",
        "geolocation": "Location",
        "geo location": "Location",
    }

    # =====================================================
    # Canonical Field Types
    # =====================================================

    FIELD_TYPES = {
        "AutoNumber",
        "Formula",
        "Summary",

        "Lookup",
        "MasterDetail",
        "ExternalLookup",

        "Checkbox",
        "Currency",
        "Date",
        "DateTime",
        "Email",
        "Location",
        "Number",
        "Percent",
        "Phone",
        "Picklist",
        "MultiselectPicklist",
        "Text",
        "TextArea",
        "LongTextArea",
        "Html",
        "EncryptedText",
        "Time",
        "Url",
    }

    # =====================================================
    # Field Configuration Schema
    #
    # These define which configuration properties our
    # application recognizes for each field family.
    #
    # Detailed validation remains in validators.
    # =====================================================

    FIELD_CONFIG_PROPERTIES = {
        "Text": {
            "length",
            "required",
        },

        "TextArea": {
            "required",
        },

        "LongTextArea": {
            "length",
            "visibleLines",
            "required",
        },

        "Html": {
            "length",
            "visibleLines",
            "required",
        },

        "EncryptedText": {
            "length",
            "maskChar",
            "maskType",
            "required",
        },

        "Email": {
            "required",
        },

        "Phone": {
            "required",
        },

        "Url": {
            "required",
        },

        "Date": {
            "required",
        },

        "DateTime": {
            "required",
        },

        "Time": {
            "required",
        },

        "Checkbox": {
            "defaultValue",
        },

        "Number": {
            "precision",
            "scale",
            "required",
        },

        "Currency": {
            "precision",
            "scale",
            "required",
        },

        "Percent": {
            "precision",
            "scale",
            "required",
        },

        "Picklist": {
            "values",
            "required",
        },

        "MultiselectPicklist": {
            "values",
            "visibleLines",
        },

        "Location": {
            "scale",
            "displayLocationInDecimal",
            "required",
        },

        "Lookup": {
            "referenceTo",
            "relationshipName",
            "deleteConstraint",
            "required",
        },

        "MasterDetail": {
            "referenceTo",
            "relationshipName",
            "reparentableMasterDetail",
            "writeRequiresMasterRead",
        },

        "ExternalLookup": {
            "referenceTo",
            "relationshipName",
            "required",
        },

        "AutoNumber": {
            "displayFormat",
            "startingNumber",
        },

        "Formula": {
            "formula",
            "formulaReturnType",
            "precision",
            "scale",
            "length",
        },

        "Summary": {
            "summaryForeignKey",
            "summaryOperation",
            "summarizedField",
        },
    }

    # =====================================================
    # Metadata Component Types
    # =====================================================

    METADATA_TYPES = {
        # Data model
        "CustomObject",
        "CustomField",
        "ValidationRule",
        "RecordType",

        # Automation
        "Flow",

        # Apex
        "ApexClass",
        "ApexTrigger",

        # Lightning UI
        "LightningComponentBundle",
        "FlexiPage",
        "Layout",

        # Application
        "CustomTab",
        "CustomApplication",

        # Security
        "PermissionSet",
    }

    # =====================================================
    # Apex Class Kinds
    # =====================================================

    APEX_CLASS_KINDS = {
        "Standard",
        "Batchable",
        "Queueable",
        "Schedulable",
        "Invocable",
        "RestResource",
        "SoapWebService",
        "Test",
        "TriggerHandler",
        "Service",
        "Controller",
    }

    # =====================================================
    # Flow Kinds
    # =====================================================

    FLOW_TYPES = {
        "Screen",
        "Autolaunched",
        "RecordTriggered",
        "ScheduledTriggered",
        "PlatformEventTriggered",
    }

    # =====================================================
    # Validation Rule Config
    # =====================================================

    VALIDATION_RULE_CONFIG_PROPERTIES = {
        "active",
        "errorConditionFormula",
        "errorMessage",
        "errorDisplayField",
    }

    # =====================================================
    # LWC Config
    # =====================================================

    LWC_CONFIG_PROPERTIES = {
        "componentKind",
        "targets",
        "isExposed",
        "apiVersion",
    }

    # =====================================================
    # Currently Executable Capabilities
    #
    # Keep this separate from known capabilities.
    #
    # A capability belongs here only after its validator,
    # deterministic generator, and automated tests are
    # implemented and passing.
    # =====================================================

    EXECUTABLE_FIELD_TYPES = {
        "AutoNumber",
        "Formula",
        "Summary",

        "Lookup",
        "MasterDetail",
        "ExternalLookup",

        "Checkbox",
        "Currency",
        "Date",
        "DateTime",
        "Email",
        "Location",
        "Number",
        "Percent",
        "Phone",
        "Picklist",
        "MultiselectPicklist",
        "Text",
        "TextArea",
        "LongTextArea",
        "Html",
        "EncryptedText",
        "Time",
        "Url",
    }

    # Flow and Apex support the contracts enforced by their validators.
    EXECUTABLE_METADATA_TYPES = {
        "Flow",
        "CustomObject",
        "CustomField",
        "ValidationRule",
        "ApexClass",
        "ApexTrigger",
    }

    # =====================================================
    # Field Helpers
    # =====================================================

    @classmethod
    def normalize_field_type(
        cls,
        value: str,
    ) -> str:
        """
        Convert a user-facing or alias field type into the
        canonical application field type.
        """

        if not isinstance(value, str):
            raise ValueError(
                "Salesforce field type must be a string."
            )

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Salesforce field type cannot be empty."
            )

        if cleaned in cls.FIELD_TYPES:
            return cleaned

        alias = cls.FIELD_TYPE_ALIASES.get(
            cleaned.lower()
        )

        if alias:
            return alias

        raise ValueError(
            f"Unsupported Salesforce field type: {value}"
        )

    @classmethod
    def is_known_field_type(
        cls,
        value: str,
    ) -> bool:
        """
        Return True when the field type is known by the
        application, even if its generator is not enabled yet.
        """

        try:
            cls.normalize_field_type(
                value
            )
            return True

        except ValueError:
            return False

    @classmethod
    def is_executable_field_type(
        cls,
        value: str,
    ) -> bool:
        """
        Return True only when the complete runtime pipeline
        currently supports this field type.
        """

        try:
            canonical = cls.normalize_field_type(
                value
            )

        except ValueError:
            return False

        return (
            canonical
            in cls.EXECUTABLE_FIELD_TYPES
        )

    @classmethod
    def get_field_config_properties(
        cls,
        value: str,
    ) -> set[str]:
        """
        Return supported application configuration keys for
        a canonical or aliased field type.
        """

        canonical = cls.normalize_field_type(
            value
        )

        return set(
            cls.FIELD_CONFIG_PROPERTIES.get(
                canonical,
                set(),
            )
        )

    # =====================================================
    # Metadata Helpers
    # =====================================================

    @classmethod
    def is_known_metadata_type(
        cls,
        metadata_type: str,
    ) -> bool:

        return (
            isinstance(
                metadata_type,
                str,
            )
            and metadata_type
            in cls.METADATA_TYPES
        )

    @classmethod
    def is_executable_metadata_type(
        cls,
        metadata_type: str,
    ) -> bool:

        return (
            isinstance(
                metadata_type,
                str,
            )
            and metadata_type
            in cls.EXECUTABLE_METADATA_TYPES
        )

    # =====================================================
    # Development Capability Helpers
    # =====================================================

    @classmethod
    def is_valid_apex_kind(
        cls,
        apex_kind: str,
    ) -> bool:

        return (
            isinstance(
                apex_kind,
                str,
            )
            and apex_kind
            in cls.APEX_CLASS_KINDS
        )

    @classmethod
    def is_valid_flow_type(
        cls,
        flow_type: str,
    ) -> bool:

        return (
            isinstance(
                flow_type,
                str,
            )
            and flow_type
            in cls.FLOW_TYPES
        )
