from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
)


class MetadataSpecStore:
    """
    Development-only in-memory store for validated
    metadata specifications.

    A specification is stored against its planId.

    This ensures deployment uses the exact metadata
    specification that was generated and reviewed,
    instead of calling the AI again.
    """

    def __init__(self):
        self._specifications: dict[
            str,
            MetadataSpecification,
        ] = {}

    def save(
        self,
        specification: MetadataSpecification,
    ) -> MetadataSpecification:
        """
        Save a validated metadata specification.
        """

        self._specifications[
            specification.planId
        ] = specification

        return specification

    def get(
        self,
        plan_id: str,
    ) -> MetadataSpecification | None:
        """
        Retrieve a metadata specification
        using its implementation plan ID.
        """

        return self._specifications.get(
            plan_id
        )

    def list(
        self,
    ) -> list[MetadataSpecification]:
        """
        Return all stored metadata specifications.
        """

        return list(
            self._specifications.values()
        )

    def delete(
        self,
        plan_id: str,
    ) -> None:
        """
        Remove a metadata specification.

        Mainly useful during development/testing.
        """

        self._specifications.pop(
            plan_id,
            None,
        )