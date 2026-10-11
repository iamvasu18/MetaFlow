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
        warnings = []

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

            if item.metadataType in {"ApexClass", "ApexTrigger"}:
                from Backend.AI.app.services.apex_validator import validate_apex_source
                config = dict(item.config or {})
                config["body"] = expected_file.read_text(encoding="utf-8")
                apex_errors, _apex_warnings = validate_apex_source(
                    item.metadataType, item.fullName, config
                )
                warnings.extend(f'{item.fullName}: {warning}' for warning in _apex_warnings)
                meta_suffix = ".cls-meta.xml" if item.metadataType == "ApexClass" else ".trigger-meta.xml"
                meta_file = expected_file.with_name(expected_file.stem + meta_suffix)
                if not meta_file.exists():
                    errors.append(f"Apex metadata file does not exist: {meta_file}")
                    continue
                try:
                    root = ET.parse(meta_file).getroot()
                    ns = 'http://soap.sforce.com/2006/04/metadata'
                    if root.tag != '{'+ns+'}'+item.metadataType or root.findtext('{'+ns+'}status') != 'Active':
                        errors.append(f'Invalid Apex metadata root/status: {meta_file}')
                        continue
                    from Backend.AI.app.services.apex_generator import _api_version
                    if root.findtext('{'+ns+'}apiVersion') != _api_version(self.project_root):
                        errors.append(f'Apex metadata API version differs from project: {meta_file}')
                        continue
                except ET.ParseError as exc:
                    errors.append(f"Invalid XML in {meta_file}: {exc}")
                    continue
                errors.extend(
                    f"{item.metadataType} {item.fullName}: {message}"
                    for message in apex_errors
                )
                if apex_errors:
                    continue

            else:
                try:
                    ET.parse(expected_file)
                except ET.ParseError as exc:
                    errors.append(
                        f"Invalid XML in "
                        f"{expected_file}: {exc}"
                    )
                    continue

            if item.metadataType == "Flow":
                from Backend.AI.app.services.flow_generator import validate_flow_artifact
                try:
                    validate_flow_artifact(expected_file, item, self.project_root)
                except ValueError as exc:
                    errors.append(str(exc))
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
            "warnings": warnings,
        }

    def _expected_file_path(
        self,
        item,
    ) -> Path | None:
        """
        Determine the expected Salesforce DX metadata
        file for a plan item.
        """

        if item.metadataType in {"Flow", "ValidationRule", "ApexClass", "ApexTrigger"}:
            from Backend.AI.app.services.profile_fls_service import component_path
            return self.project_root / component_path(item.metadataType, item.fullName)

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
