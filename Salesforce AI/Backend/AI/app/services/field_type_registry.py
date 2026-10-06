from __future__ import annotations

from Backend.AI.app.services.salesforce_capability_registry import (
    SalesforceCapabilityRegistry,
)


class SalesforceFieldTypeRegistry:
    """
    Backward-compatible Salesforce custom field type registry.

    The SalesforceCapabilityRegistry is now the single
    source of truth.

    Responsibilities:
    - Normalize natural-language / AI field type names.
    - Return canonical Salesforce field types.
    - Check whether a field type is known.
    - Check whether a field type is currently executable.
    - Preserve the existing SalesforceFieldTypeRegistry API.

    This class does NOT:
    - generate XML
    - validate field-specific configuration
    - deploy metadata
    """

    # =====================================================
    # Backward-Compatible Registry Attributes
    # =====================================================

    # Keep these attributes because existing application code
    # or tests may reference them directly.
    #
    # Their values now come from the central capability
    # registry instead of being duplicated here.

    _ALIASES = (
        SalesforceCapabilityRegistry.FIELD_TYPE_ALIASES
    )

    _SUPPORTED_TYPES = (
        SalesforceCapabilityRegistry.FIELD_TYPES
    )

    # =====================================================
    # Normalize Field Type
    # =====================================================

    @classmethod
    def normalize(
        cls,
        field_type: str,
    ) -> str:
        """
        Normalize a user/AI supplied field type into the
        canonical application field type.

        Examples:

            "Rich Text Area"
                -> "Html"

            "Date/Time"
                -> "DateTime"

            "Multi-Select Picklist"
                -> "MultiselectPicklist"

            "Lookup Relationship"
                -> "Lookup"

            "Master-Detail Relationship"
                -> "MasterDetail"

            "External Lookup Relationship"
                -> "ExternalLookup"

            "Roll-Up Summary"
                -> "Summary"

            "Geolocation"
                -> "Location"

        Canonical values are also accepted:

            "Text"
            "Html"
            "Lookup"
            "MasterDetail"
            "Formula"
        """

        return (
            SalesforceCapabilityRegistry
            .normalize_field_type(
                field_type
            )
        )

    # =====================================================
    # Known / Supported Field Type
    # =====================================================

    @classmethod
    def is_supported(
        cls,
        field_type: str,
    ) -> bool:
        """
        Return True when the field type is recognized by
        the Salesforce capability registry.

        Important:

        "supported" here preserves the historical meaning
        of SalesforceFieldTypeRegistry.is_supported():

        the field type is known by the application.

        It does NOT necessarily mean that the complete
        validator + generator + deployment pipeline has
        been implemented for that field type yet.

        Use is_executable() for that distinction.
        """

        return (
            SalesforceCapabilityRegistry
            .is_known_field_type(
                field_type
            )
        )

    # =====================================================
    # Executable Field Type
    # =====================================================

    @classmethod
    def is_executable(
        cls,
        field_type: str,
    ) -> bool:
        """
        Return True only when the complete CREATE pipeline
        currently supports the field type.

        This means that the field type has working:

        - planning support
        - metadata specification support
        - validation
        - deterministic metadata generation
        - deployment support
        """

        return (
            SalesforceCapabilityRegistry
            .is_executable_field_type(
                field_type
            )
        )

    # =====================================================
    # All Known Field Types
    # =====================================================

    @classmethod
    def supported_types(
        cls,
    ) -> list[str]:
        """
        Return all Salesforce field types currently known
        by the application.

        This is intentionally broader than the set that is
        currently executable.
        """

        return sorted(
            SalesforceCapabilityRegistry.FIELD_TYPES
        )

    # =====================================================
    # Currently Executable Field Types
    # =====================================================

    @classmethod
    def executable_types(
        cls,
    ) -> list[str]:
        """
        Return field types whose complete runtime pipeline
        is currently implemented.
        """

        return sorted(
            SalesforceCapabilityRegistry
            .EXECUTABLE_FIELD_TYPES
        )

    # =====================================================
    # Field Configuration Properties
    # =====================================================

    @classmethod
    def config_properties(
        cls,
        field_type: str,
    ) -> set[str]:
        """
        Return application-recognized configuration
        properties for a field type.

        Example:

            config_properties("Lookup")

        returns properties such as:

            referenceTo
            relationshipName
            deleteConstraint
            required

        Detailed value validation is handled by the
        validator layer.
        """

        return (
            SalesforceCapabilityRegistry
            .get_field_config_properties(
                field_type
            )
        )