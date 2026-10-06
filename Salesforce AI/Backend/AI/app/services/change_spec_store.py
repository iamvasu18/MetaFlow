from Backend.AI.app.validators.change_spec_validator import (
    ChangeSpecification,
)


class ChangeSpecStore:
    """
    Development-only in-memory store for validated
    Salesforce Change Specifications.

    A ChangeSpecification is stored against its planId.

    This prevents deployment from calling the AI again
    and producing a different change specification.
    """

    def __init__(self):

        self._specifications: dict[
            str,
            ChangeSpecification,
        ] = {}

    def save(
        self,
        specification: ChangeSpecification,
    ) -> ChangeSpecification:
        """
        Save a validated ChangeSpecification.
        """

        self._specifications[
            specification.planId
        ] = specification

        return specification

    def get(
        self,
        plan_id: str,
    ) -> ChangeSpecification | None:
        """
        Retrieve a ChangeSpecification by plan ID.
        """

        return self._specifications.get(
            plan_id
        )

    def list(
        self,
    ) -> list[ChangeSpecification]:
        """
        Return all stored ChangeSpecifications.
        """

        return list(
            self._specifications.values()
        )

    def delete(
        self,
        plan_id: str,
    ) -> None:
        """
        Remove a stored ChangeSpecification.
        """

        self._specifications.pop(
            plan_id,
            None,
        )