from pathlib import Path
import xml.etree.ElementTree as ET

from Backend.AI.app.validators.change_spec_validator import (
    ChangeSpecification,
    ChangeItem,
)


# =========================================================
# Salesforce Metadata XML Namespace
# =========================================================

SALESFORCE_METADATA_NS = (
    "http://soap.sforce.com/2006/04/metadata"
)

ET.register_namespace(
    "",
    SALESFORCE_METADATA_NS,
)


def _tag(
    name: str,
) -> str:
    """
    Build a Salesforce metadata XML namespaced tag.
    """

    return (
        f"{{{SALESFORCE_METADATA_NS}}}"
        f"{name}"
    )


# =========================================================
# Change Generator
# =========================================================

class SalesforceChangeGenerator:
    """
    Applies validated ChangeSpecification UPDATE operations
    to existing Salesforce DX metadata XML files.

    Supported in Change v001:

    CustomObject:
    - label
    - pluralLabel

    CustomField:
    - label
    - required
    - addPicklistValues

    This service does NOT:

    - call an AI provider
    - create new metadata
    - delete metadata
    - execute Salesforce CLI
    - deploy to Salesforce
    """

    def __init__(
        self,
        project_root: str | Path = ".",
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
    # Public API
    # =====================================================

    def apply(
        self,
        specification: ChangeSpecification,
    ) -> list[str]:
        """
        Apply a validated ChangeSpecification to local
        Salesforce metadata files.

        Returns the paths of modified files.
        """

        if specification.validationIssues:

            raise ValueError(
                "Cannot apply a ChangeSpecification "
                "that contains validation issues."
            )

        modified_files: list[str] = []

        for change in specification.changes:

            if change.action != "UPDATE":

                raise ValueError(
                    "Change generator supports "
                    "UPDATE actions only."
                )

            if change.metadataType == "CustomObject":

                file_path = (
                    self._apply_custom_object_change(
                        change
                    )
                )

            elif change.metadataType == "CustomField":

                file_path = (
                    self._apply_custom_field_change(
                        change
                    )
                )

            else:

                raise ValueError(
                    "Unsupported metadata type: "
                    f"{change.metadataType}"
                )

            normalized_path = str(
                file_path.relative_to(
                    self.project_root
                )
            )

            if (
                normalized_path
                not in modified_files
            ):

                modified_files.append(
                    normalized_path
                )

        return modified_files

    # =====================================================
    # Local Source Path Resolution
    # =====================================================

    @staticmethod
    def _without_namespace(
        api_name: str,
    ) -> str:
        """
        Return the local source API name Salesforce CLI may
        use when retrieved metadata strips a namespace.

        Examples:

        LayaDevHub__AI_Test_Session__c
            -> AI_Test_Session__c

        LayaDevHub__Status__c
            -> Status__c

        AI_Test_Session__c
            -> AI_Test_Session__c

        The namespace value is never hard-coded.
        """

        value = str(
            api_name or ""
        ).strip()

        if not value:
            return value

        parts = value.split(
            "__"
        )

        # Normal custom API name:
        # AI_Test_Session__c
        # -> ["AI_Test_Session", "c"]
        #
        # Namespaced custom API name:
        # LayaDevHub__AI_Test_Session__c
        # -> ["LayaDevHub", "AI_Test_Session", "c"]
        #
        # Only strip the first segment when Salesforce's
        # namespace shape is actually present.
        if (
            len(parts) >= 3
            and parts[-1].lower()
            in {
                "c",
                "r",
            }
        ):
            return "__".join(
                parts[1:]
            )

        return value

    def _get_metadata_roots(
        self,
    ) -> list[Path]:
        """
        Return supported local metadata roots.

        Standard Salesforce DX project:

            <project>/force-app/main/default/objects

        Salesforce CLI --output-dir retrieval:

            <output-dir>/objects

        Supporting both lets the change generator operate on
        a retrieved staging copy without modifying force-app.
        """

        roots = [
            self.metadata_root,
            self.project_root,
        ]

        unique_roots: list[Path] = []

        for root in roots:

            if root not in unique_roots:

                unique_roots.append(
                    root
                )

        return unique_roots

    @staticmethod
    def _unique_paths(
        paths: list[Path],
    ) -> list[Path]:

        unique: list[Path] = []

        for path in paths:

            if path not in unique:

                unique.append(
                    path
                )

        return unique

    def _resolve_existing_metadata_file(
        self,
        exact_candidates: list[Path],
        fallback_candidates: list[Path],
        full_name: str,
    ) -> Path:
        """
        Resolve exactly one local metadata file.

        Exact API-name paths always win.

        Namespace-stripped fallback paths are used only when
        no exact path exists.

        If more than one file matches at the same priority,
        fail safely rather than modifying an ambiguous file.
        """

        exact_candidates = (
            self._unique_paths(
                exact_candidates
            )
        )

        fallback_candidates = (
            self._unique_paths(
                fallback_candidates
            )
        )

        exact_existing = [
            path
            for path in exact_candidates
            if path.exists()
        ]

        if len(
            exact_existing
        ) == 1:

            return exact_existing[0]

        if len(
            exact_existing
        ) > 1:

            raise ValueError(
                "Ambiguous Salesforce metadata source for "
                f"{full_name}. Multiple exact files exist: "
                + ", ".join(
                    str(path)
                    for path in exact_existing
                )
            )

        fallback_existing = [
            path
            for path in fallback_candidates
            if path.exists()
        ]

        if len(
            fallback_existing
        ) == 1:

            return fallback_existing[0]

        if len(
            fallback_existing
        ) > 1:

            raise ValueError(
                "Ambiguous Salesforce metadata source for "
                f"{full_name}. Multiple namespace-resolved "
                "files exist: "
                + ", ".join(
                    str(path)
                    for path in fallback_existing
                )
            )

        attempted_paths = (
            exact_candidates
            + fallback_candidates
        )

        raise FileNotFoundError(
            "Salesforce metadata file not found for "
            f"{full_name}. Tried: "
            + ", ".join(
                str(path)
                for path in attempted_paths
            )
        )

    def _resolve_custom_object_file(
        self,
        object_name: str,
    ) -> Path:
        """
        Resolve a CustomObject XML file using either the exact
        org API name or Salesforce CLI's namespace-stripped
        retrieved-source name.
        """

        roots = (
            self._get_metadata_roots()
        )

        exact_candidates = [
            (
                root
                / "objects"
                / object_name
                / (
                    f"{object_name}"
                    ".object-meta.xml"
                )
            )
            for root in roots
        ]

        local_object_name = (
            self._without_namespace(
                object_name
            )
        )

        fallback_candidates: list[Path] = []

        if (
            local_object_name
            != object_name
        ):

            fallback_candidates = [
                (
                    root
                    / "objects"
                    / local_object_name
                    / (
                        f"{local_object_name}"
                        ".object-meta.xml"
                    )
                )
                for root in roots
            ]

        return (
            self._resolve_existing_metadata_file(
                exact_candidates=(
                    exact_candidates
                ),
                fallback_candidates=(
                    fallback_candidates
                ),
                full_name=object_name,
            )
        )

    def _resolve_custom_field_file(
        self,
        object_name: str,
        field_name: str,
    ) -> Path:
        """
        Resolve a CustomField XML file.

        Org identity remains exact, for example:

            LayaDevHub__AI_Test_Session__c.
            LayaDevHub__Status__c

        But a Salesforce CLI retrieval may materialize it as:

            objects/
              AI_Test_Session__c/
                fields/
                  Status__c.field-meta.xml

        This method performs that mapping without hard-coding
        any namespace.
        """

        roots = (
            self._get_metadata_roots()
        )

        exact_candidates = [
            (
                root
                / "objects"
                / object_name
                / "fields"
                / (
                    f"{field_name}"
                    ".field-meta.xml"
                )
            )
            for root in roots
        ]

        local_object_name = (
            self._without_namespace(
                object_name
            )
        )

        local_field_name = (
            self._without_namespace(
                field_name
            )
        )

        fallback_name_pairs = []

        # Mixed forms are supported because managed-package
        # fields can exist on standard or differently represented
        # objects in retrieved source.
        possible_pairs = [
            (
                object_name,
                local_field_name,
            ),
            (
                local_object_name,
                field_name,
            ),
            (
                local_object_name,
                local_field_name,
            ),
        ]

        for pair in possible_pairs:

            if pair == (
                object_name,
                field_name,
            ):
                continue

            if (
                pair
                not in fallback_name_pairs
            ):

                fallback_name_pairs.append(
                    pair
                )

        fallback_candidates = []

        for (
            candidate_object,
            candidate_field,
        ) in fallback_name_pairs:

            for root in roots:

                fallback_candidates.append(
                    (
                        root
                        / "objects"
                        / candidate_object
                        / "fields"
                        / (
                            f"{candidate_field}"
                            ".field-meta.xml"
                        )
                    )
                )

        return (
            self._resolve_existing_metadata_file(
                exact_candidates=(
                    exact_candidates
                ),
                fallback_candidates=(
                    fallback_candidates
                ),
                full_name=(
                    f"{object_name}."
                    f"{field_name}"
                ),
            )
        )

    # =====================================================
    # Custom Object
    # =====================================================

    def _apply_custom_object_change(
        self,
        change: ChangeItem,
    ) -> Path:

        object_name = change.fullName

        file_path = (
            self._resolve_custom_object_file(
                object_name
            )
        )

        root, tree = (
            self._load_xml_file(
                file_path
            )
        )

        changes = change.changes

        # -------------------------------------------------
        # Label
        # -------------------------------------------------

        if "label" in changes:

            self._apply_text_change(
                root=root,
                tag_name="label",
                change_data=changes[
                    "label"
                ],
                full_name=change.fullName,
            )

        # -------------------------------------------------
        # Plural Label
        # -------------------------------------------------

        if "pluralLabel" in changes:

            self._apply_text_change(
                root=root,
                tag_name="pluralLabel",
                change_data=changes[
                    "pluralLabel"
                ],
                full_name=change.fullName,
            )

        self._write_xml(
            tree=tree,
            file_path=file_path,
        )

        return file_path

    # =====================================================
    # Custom Field
    # =====================================================

    def _apply_custom_field_change(
        self,
        change: ChangeItem,
    ) -> Path:

        try:

            object_name, field_name = (
                change.fullName.split(
                    ".",
                    1,
                )
            )

        except ValueError as exc:

            raise ValueError(
                "Invalid CustomField fullName: "
                f"{change.fullName}"
            ) from exc

        file_path = (
            self._resolve_custom_field_file(
                object_name=object_name,
                field_name=field_name,
            )
        )

        root, tree = (
            self._load_xml_file(
                file_path
            )
        )

        changes = change.changes

        # -------------------------------------------------
        # Label
        # -------------------------------------------------

        if "label" in changes:

            self._apply_text_change(
                root=root,
                tag_name="label",
                change_data=changes[
                    "label"
                ],
                full_name=change.fullName,
            )

        # -------------------------------------------------
        # Required
        # -------------------------------------------------

        if "required" in changes:

            self._apply_required_change(
                root=root,
                change_data=changes[
                    "required"
                ],
                full_name=change.fullName,
            )

        # -------------------------------------------------
        # Picklist values
        # -------------------------------------------------

        if "addPicklistValues" in changes:

            self._add_picklist_values(
                root=root,
                values=changes[
                    "addPicklistValues"
                ],
                full_name=change.fullName,
            )

        self._write_xml(
            tree=tree,
            file_path=file_path,
        )

        return file_path

    # =====================================================
    # Text Change
    # =====================================================

    def _apply_text_change(
        self,
        root: ET.Element,
        tag_name: str,
        change_data: dict,
        full_name: str,
    ) -> None:
        """
        Apply a from -> to string change.

        The current XML value must exactly match `from`.
        """

        element = root.find(
            _tag(tag_name)
        )

        if element is None:

            raise ValueError(
                f"{full_name} does not contain "
                f"XML property '{tag_name}'."
            )

        current_value = (
            element.text or ""
        ).strip()

        expected_value = (
            change_data["from"]
        )

        new_value = (
            change_data["to"]
        )

        if current_value != expected_value:

            raise ValueError(
                f"{full_name} {tag_name} mismatch. "
                f"Expected existing value "
                f"{expected_value!r}, "
                f"but XML contains "
                f"{current_value!r}."
            )

        element.text = new_value

    # =====================================================
    # Required Change
    # =====================================================

    def _apply_required_change(
        self,
        root: ET.Element,
        change_data: dict,
        full_name: str,
    ) -> None:

        element = root.find(
            _tag("required")
        )

        expected_value = (
            change_data["from"]
        )

        new_value = (
            change_data["to"]
        )

        # -------------------------------------------------
        # Salesforce may omit <required> when false.
        # Treat missing as false.
        # -------------------------------------------------

        if element is None:

            current_value = False

        else:

            text_value = (
                element.text or ""
            ).strip().lower()

            current_value = (
                text_value == "true"
            )

        if current_value != expected_value:

            raise ValueError(
                f"{full_name} required mismatch. "
                f"Expected existing value "
                f"{expected_value!r}, "
                f"but XML contains "
                f"{current_value!r}."
            )

        if element is None:

            element = ET.SubElement(
                root,
                _tag("required"),
            )

        element.text = (
            "true"
            if new_value
            else "false"
        )

    # =====================================================
    # Picklist Values
    # =====================================================

    def _add_picklist_values(
        self,
        root: ET.Element,
        values: list[str],
        full_name: str,
    ) -> None:

        field_type = root.find(
            _tag("type")
        )

        if field_type is None:

            raise ValueError(
                f"{full_name} does not contain "
                "a field type."
            )

        type_value = (
            field_type.text or ""
        ).strip()

        if type_value != "Picklist":

            raise ValueError(
                f"{full_name} is not a Picklist field. "
                f"Current type is {type_value!r}."
            )

        value_set = root.find(
            _tag("valueSet")
        )

        if value_set is None:

            raise ValueError(
                f"{full_name} does not contain "
                "a valueSet."
            )

        # -------------------------------------------------
        # Global Value Set safety
        # -------------------------------------------------

        value_set_name = value_set.find(
            _tag("valueSetName")
        )

        if value_set_name is not None:

            raise ValueError(
                f"{full_name} uses a Global Value Set. "
                "Change v001 does not support modifying "
                "Global Value Sets."
            )

        definition = value_set.find(
            _tag("valueSetDefinition")
        )

        if definition is None:

            raise ValueError(
                f"{full_name} does not contain "
                "a local valueSetDefinition."
            )

        # -------------------------------------------------
        # Read existing values
        # -------------------------------------------------

        existing_values: set[str] = set()

        for value_element in definition.findall(
            _tag("value")
        ):

            full_name_element = (
                value_element.find(
                    _tag("fullName")
                )
            )

            if (
                full_name_element is not None
                and full_name_element.text
            ):

                existing_values.add(
                    full_name_element.text.strip()
                )

        # -------------------------------------------------
        # Add requested values
        # -------------------------------------------------

        for value in values:

            if value in existing_values:

                raise ValueError(
                    f"Picklist value {value!r} "
                    f"already exists in "
                    f"{full_name}."
                )

            value_element = ET.SubElement(
                definition,
                _tag("value"),
            )

            full_name_element = (
                ET.SubElement(
                    value_element,
                    _tag("fullName"),
                )
            )

            full_name_element.text = value

            default_element = (
                ET.SubElement(
                    value_element,
                    _tag("default"),
                )
            )

            default_element.text = "false"

            existing_values.add(
                value
            )

    # =====================================================
    # XML Helpers
    # =====================================================

    @staticmethod
    def _load_xml_file(
        file_path: Path,
    ) -> tuple[
        ET.Element,
        ET.ElementTree,
    ]:

        if not file_path.exists():

            raise FileNotFoundError(
                "Salesforce metadata file "
                f"not found: {file_path}"
            )

        try:

            tree = ET.parse(
                file_path
            )

        except ET.ParseError as exc:

            raise ValueError(
                "Invalid Salesforce metadata XML: "
                f"{file_path}"
            ) from exc

        root = tree.getroot()

        return (
            root,
            tree,
        )

    # =====================================================
    # XML Writer
    # =====================================================

    @staticmethod
    def _write_xml(
        tree: ET.ElementTree,
        file_path: Path,
    ) -> None:

        tree.write(
            file_path,
            encoding="UTF-8",
            xml_declaration=True,
        )