from pathlib import Path
import xml.etree.ElementTree as ET

from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


class SalesforceMetadataValidator:
    """
    Validates Salesforce DX metadata generated from
    an approved implementation plan.

    This service performs local validation only.

    It does NOT deploy anything to Salesforce.
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

    def validate_plan(
        self,
        plan: ImplementationPlan,
    ) -> None:
        """
        Only APPROVED plans can be validated for deployment.
        """

        if plan.status != "APPROVED":

            raise ValueError(
                "Only APPROVED plans can be validated."
            )

    def validate(
        self,
        plan: ImplementationPlan,
    ) -> dict:
        """
        Validate metadata files associated with the plan.

        Returns a validation result.
        """

        self.validate_plan(
            plan
        )

        errors = []
        validated_files = []

        for item in plan.items:

            if item.action != "CREATE":
                continue

            expected_file = (
                self._expected_file_path(
                    item
                )
            )

            if expected_file is None:
                continue

            if not expected_file.exists():

                errors.append(
                    f"Metadata file does not exist: "
                    f"{expected_file}"
                )

                continue

            try:

                ET.parse(
                    expected_file
                )

            except ET.ParseError as exc:

                errors.append(
                    f"Invalid XML in "
                    f"{expected_file}: {exc}"
                )

                continue

            validated_files.append(
                str(expected_file)
            )

        return {
            "valid": len(errors) == 0,
            "planId": plan.id,
            "status": plan.status,
            "validatedFiles": validated_files,
            "errors": errors,
        }

    def _expected_file_path(
        self,
        item,
    ) -> Path | None:
        """
        Determine the expected Salesforce DX metadata
        file for a plan item.
        """

        if item.metadataType == "CustomObject":

            return (
                self.metadata_root
                / "objects"
                / item.fullName
                / f"{item.fullName}.object-meta.xml"
            )

        if item.metadataType == "CustomField":

            parts = item.fullName.split(
                ".",
                1,
            )

            if len(parts) != 2:
                return None

            object_name = parts[0]
            field_name = parts[1]

            return (
                self.metadata_root
                / "objects"
                / object_name
                / "fields"
                / f"{field_name}.field-meta.xml"
            )

        return None