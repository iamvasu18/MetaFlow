import json
import os
import re
import shutil
import subprocess


class SalesforceMetadataService:
    """
    Retrieves Salesforce object, field, relationship,
    and picklist metadata using Salesforce CLI.
    """

    def __init__(
        self,
        target_org: str,
    ):
        self.target_org = target_org

    # =====================================================
    # Salesforce CLI
    # =====================================================

    def _run_sf_command(
        self,
        command: list[str],
    ) -> dict:
        """
        Execute an sf CLI command and return parsed JSON.

        On Windows, Salesforce CLI is commonly installed at a
        path such as:

            C:\\Program Files\\sf\\bin\\sf.CMD

        Build one correctly quoted command line and let cmd.exe
        execute it so spaces in the executable path and SOQL
        query arguments are preserved.
        """

        sf_command = shutil.which("sf")

        if not sf_command:
            raise RuntimeError(
                "Salesforce CLI 'sf' was not found in PATH."
            )

        # Replace the generic "sf" entry with the exact
        # executable discovered from PATH.
        command = [
            sf_command,
            *command[1:],
        ]

        # Quote every argument correctly for Windows.
        command_line = subprocess.list2cmdline(
            command
        )

        comspec = os.environ.get(
            "COMSPEC",
            "cmd.exe",
        )

        result = subprocess.run(
            command_line,
            shell=True,
            executable=comspec,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        stdout = (
            result.stdout.strip()
            if result.stdout
            else ""
        )

        stderr = (
            result.stderr.strip()
            if result.stderr
            else ""
        )

        # -------------------------------------------------
        # Command Failed
        # -------------------------------------------------

        if result.returncode != 0:

            error_message = None

            # With --json Salesforce normally places the
            # structured error in stdout.
            if stdout:

                try:
                    error_data = json.loads(
                        stdout
                    )

                    if isinstance(
                        error_data,
                        dict,
                    ):

                        error_message = (
                            error_data.get(
                                "message"
                            )
                            or error_data.get(
                                "name"
                            )
                        )

                        if (
                            not error_message
                            and isinstance(
                                error_data.get(
                                    "result"
                                ),
                                dict,
                            )
                        ):

                            result_data = (
                                error_data[
                                    "result"
                                ]
                            )

                            error_message = (
                                result_data.get(
                                    "message"
                                )
                                or result_data.get(
                                    "error"
                                )
                            )

                    if not error_message:
                        error_message = stdout

                except json.JSONDecodeError:
                    error_message = stdout

            # stderr often contains Salesforce CLI update
            # warnings, so use it only as a fallback.
            if not error_message:
                error_message = (
                    stderr
                    or
                    "Unknown Salesforce CLI error."
                )

            raise RuntimeError(
                "Salesforce CLI command failed "
                f"(exit code {result.returncode}): "
                f"{error_message}"
            )

        # -------------------------------------------------
        # Successful Command But No Output
        # -------------------------------------------------

        if not stdout:
            raise RuntimeError(
                "Salesforce CLI returned no JSON output."
            )

        # -------------------------------------------------
        # Parse Successful JSON
        # -------------------------------------------------

        try:
            parsed = json.loads(
                stdout
            )

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Salesforce CLI returned invalid JSON. "
                f"Output: {stdout[:1000]}"
            ) from exc

        if not isinstance(
            parsed,
            dict,
        ):
            raise RuntimeError(
                "Salesforce CLI returned an unexpected "
                "JSON response."
            )

        return parsed

    # =====================================================
    # Object Discovery
    # =====================================================

    def list_objects(
        self,
    ) -> list[dict]:
        """
        Retrieve Salesforce objects available in the org.
        """

        command = [
            "sf",
            "sobject",
            "list",
            "--target-org",
            self.target_org,
            "--json",
        ]

        data = self._run_sf_command(command)

        result = data.get(
            "result",
            [],
        )

        objects = []

        for item in result:

            if isinstance(item, str):

                objects.append(
                    {
                        "name": item,
                        "fullName": item,
                        "label": None,
                    }
                )

            elif isinstance(item, dict):

                name = item.get("name")

                if not name:
                    continue

                objects.append(
                    {
                        "name": name,
                        "fullName": name,
                        "label": item.get("label"),
                    }
                )

        return objects

    # =====================================================
    # Metadata Name Tokenizer
    # =====================================================

    def _tokenize_metadata_name(
        self,
        value: str,
    ) -> set[str]:
        """
        Convert API names, labels and natural language
        into comparable lowercase words.
        """

        if not value:
            return set()

        cleaned = str(value).strip()

        if not cleaned:
            return set()

        # Remove Salesforce custom suffix.
        cleaned = re.sub(
            r"__(c|r)$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = cleaned.replace(
            "_",
            " ",
        )

        # Split camel case.
        cleaned = re.sub(
            r"(?<=[a-z0-9])(?=[A-Z])",
            " ",
            cleaned,
        )

        terms = set(
            re.findall(
                r"[A-Za-z0-9]+",
                cleaned.lower(),
            )
        )

        terms.discard("c")
        terms.discard("r")

        return terms

    # =====================================================
    # Relevant Object Discovery
    # =====================================================

    def find_relevant_objects(
        self,
        requirement: str,
        max_objects: int = 10,
    ) -> list[str]:
        """
        Find Salesforce objects relevant to a natural
        language requirement.
        """

        if not isinstance(requirement, str):
            raise ValueError(
                "Requirement must be a string."
            )

        if not requirement.strip():
            return []

        if max_objects <= 0:
            return []

        requirement_terms = (
            self._tokenize_metadata_name(
                requirement
            )
        )

        if not requirement_terms:
            return []

        objects = self.list_objects()

        scored_objects = []

        for obj in objects:

            name = str(
                obj.get(
                    "name",
                    "",
                )
                or ""
            )

            label = str(
                obj.get(
                    "label",
                    "",
                )
                or ""
            )

            if not name:
                continue

            name_terms = (
                self._tokenize_metadata_name(
                    name
                )
            )

            label_terms = (
                self._tokenize_metadata_name(
                    label
                )
            )

            searchable_terms = (
                name_terms
                | label_terms
            )

            if not searchable_terms:
                continue

            matched_terms = (
                requirement_terms.intersection(
                    searchable_terms
                )
            )

            score = len(matched_terms)

            if score == 0:
                continue

            if (
                name_terms
                and name_terms.issubset(
                    requirement_terms
                )
            ):
                score += 100

            if (
                label_terms
                and label_terms.issubset(
                    requirement_terms
                )
            ):
                score += 100

            if name_terms:

                name_match_ratio = (
                    len(
                        requirement_terms.intersection(
                            name_terms
                        )
                    )
                    / len(name_terms)
                )

                score += (
                    name_match_ratio
                    * 10
                )

            if label_terms:

                label_match_ratio = (
                    len(
                        requirement_terms.intersection(
                            label_terms
                        )
                    )
                    / len(label_terms)
                )

                score += (
                    label_match_ratio
                    * 10
                )

            scored_objects.append(
                (
                    score,
                    name,
                )
            )

        scored_objects.sort(
            key=lambda item: (
                -item[0],
                item[1].lower(),
            )
        )

        return [
            name
            for _, name
            in scored_objects[:max_objects]
        ]

    # =====================================================
    # Field Type Normalization
    # =====================================================

    @staticmethod
    def _normalize_field_type(
        data_type: str,
    ) -> str:
        """
        Convert FieldDefinition.DataType into the
        normalized types used by the AI context.
        """

        value = str(
            data_type or ""
        ).strip()

        if not value:
            return ""

        base_type = (
            value
            .split("(", 1)[0]
            .strip()
            .lower()
        )

        mapping = {
            "picklist": "picklist",
            "multipicklist": "multipicklist",
            "multi-select picklist": "multipicklist",
            "email": "email",
            "date": "date",
            "date/time": "datetime",
            "datetime": "datetime",
            "checkbox": "boolean",
            "boolean": "boolean",
            "currency": "currency",
            "number": "number",
            "percent": "percent",
            "phone": "phone",
            "url": "url",
            "text": "string",
            "textarea": "textarea",
            "long textarea": "textarea",
            "rich textarea": "textarea",
            "auto number": "string",
            "lookup": "reference",
            "master-detail": "reference",
        }

        return mapping.get(
            base_type,
            base_type,
        )

    # =====================================================
    # FieldDefinition Metadata Discovery
    # =====================================================

    def get_field_definitions(
        self,
        object_name: str,
    ) -> list[dict]:
        """
        Retrieve fields using Salesforce FieldDefinition.

        This supplements `sf sobject describe`.

        FieldDefinition can expose Salesforce metadata fields
        that runtime describe does not return for the current
        authenticated user.

        Exact QualifiedApiName values are preserved, including
        namespace prefixes.
        """

        if not isinstance(
            object_name,
            str,
        ):
            raise ValueError(
                "Salesforce object name must be a string."
            )

        object_name = object_name.strip()

        if not object_name:
            raise ValueError(
                "Salesforce object name cannot be empty."
            )

        escaped_object_name = (
            object_name.replace(
                "'",
                "\\'",
            )
        )

        query = (
            "SELECT QualifiedApiName, Label, DataType "
            "FROM FieldDefinition "
            "WHERE EntityDefinition.QualifiedApiName = "
            f"'{escaped_object_name}'"
        )

        command = [
            "sf",
            "data",
            "query",
            "--query",
            query,
            "--target-org",
            self.target_org,
            "--use-tooling-api",
            "--json",
        ]

        data = self._run_sf_command(
            command
        )

        result = data.get(
            "result",
            {},
        )

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                "Salesforce FieldDefinition query returned "
                "an unexpected result."
            )

        records = result.get(
            "records",
            [],
        )

        fields = []

        for record in records:

            if not isinstance(
                record,
                dict,
            ):
                continue

            api_name = record.get(
                "QualifiedApiName"
            )

            if not api_name:
                continue

            raw_data_type = str(
                record.get(
                    "DataType"
                )
                or ""
            ).strip()

            fields.append(
                {
                    "name": api_name,

                    "fullName": (
                        f"{object_name}.{api_name}"
                    ),

                    "label": record.get(
                        "Label"
                    ),

                    "type": (
                        self._normalize_field_type(
                            raw_data_type
                        )
                    ),

                    "rawDataType": raw_data_type,

                    # FieldDefinition query currently does
                    # not determine required status.
                    "required": None,
                }
            )

        return fields

    # =====================================================
    # Object Describe
    # =====================================================

    def describe_object(
        self,
        object_name: str,
    ) -> dict:
        """
        Retrieve fields, relationships and supported
        picklist information for one Salesforce object.

        Field information comes from two sources:

        1. sf sobject describe
        2. FieldDefinition Tooling API

        They are merged using the exact Salesforce API name.
        """

        if not isinstance(
            object_name,
            str,
        ):
            raise ValueError(
                "Salesforce object name must be a string."
            )

        object_name = object_name.strip()

        if not object_name:
            raise ValueError(
                "Salesforce object name cannot be empty."
            )

        # -------------------------------------------------
        # Runtime Describe
        # -------------------------------------------------

        command = [
            "sf",
            "sobject",
            "describe",
            "--sobject",
            object_name,
            "--target-org",
            self.target_org,
            "--json",
        ]

        data = self._run_sf_command(
            command
        )

        result = data.get(
            "result",
            {},
        )

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                "Salesforce describe returned an "
                "unexpected result."
            )

        fields = []
        relationships = []

        for field in result.get(
            "fields",
            [],
        ):

            if not isinstance(
                field,
                dict,
            ):
                continue

            field_name = field.get(
                "name"
            )

            field_type = field.get(
                "type"
            )

            field_data = {
                "name": field_name,

                "fullName": (
                    f"{object_name}.{field_name}"
                    if field_name
                    else None
                ),

                "label": field.get(
                    "label"
                ),

                "type": field_type,

                "required": (
                    field.get(
                        "nillable"
                    )
                    is False
                ),
            }

            # ---------------------------------------------
            # Picklist Values
            # ---------------------------------------------

            if field_type in {
                "picklist",
                "multipicklist",
            }:

                picklist_values = []

                for value in field.get(
                    "picklistValues",
                    [],
                ):

                    if not isinstance(
                        value,
                        dict,
                    ):
                        continue

                    if not value.get(
                        "active",
                        True,
                    ):
                        continue

                    actual_value = value.get(
                        "value"
                    )

                    if actual_value is None:
                        continue

                    picklist_values.append(
                        actual_value
                    )

                field_data[
                    "values"
                ] = picklist_values

            # ---------------------------------------------
            # Relationships
            # ---------------------------------------------

            reference_to = field.get(
                "referenceTo",
                [],
            )

            relationship_name = field.get(
                "relationshipName"
            )

            if reference_to:

                field_data[
                    "referenceTo"
                ] = reference_to

                if relationship_name:

                    field_data[
                        "relationshipName"
                    ] = relationship_name

                relationships.append(
                    {
                        "field": field_name,
                        "type": field_type,
                        "referenceTo": reference_to,
                        "relationshipName": (
                            relationship_name
                        ),
                    }
                )

            fields.append(
                field_data
            )

        # -------------------------------------------------
        # FieldDefinition Metadata
        # -------------------------------------------------

        metadata_fields = (
            self.get_field_definitions(
                object_name
            )
        )

        # Existing fields returned by runtime describe.
        existing_fields_by_name = {
            field.get("name"): field
            for field in fields
            if field.get("name")
        }

        # -------------------------------------------------
        # Merge Metadata Fields
        # -------------------------------------------------

        for metadata_field in metadata_fields:

            field_name = metadata_field.get(
                "name"
            )

            if not field_name:
                continue

            # ---------------------------------------------
            # Field already returned by describe
            # ---------------------------------------------

            if field_name in existing_fields_by_name:

                existing_field = (
                    existing_fields_by_name[
                        field_name
                    ]
                )

                # Preserve exact Salesforce API identity.
                existing_field[
                    "name"
                ] = field_name

                existing_field[
                    "fullName"
                ] = metadata_field.get(
                    "fullName"
                )

                if not existing_field.get(
                    "label"
                ):
                    existing_field[
                        "label"
                    ] = metadata_field.get(
                        "label"
                    )

                if not existing_field.get(
                    "type"
                ):
                    existing_field[
                        "type"
                    ] = metadata_field.get(
                        "type"
                    )

                existing_field[
                    "rawDataType"
                ] = metadata_field.get(
                    "rawDataType"
                )

            # ---------------------------------------------
            # Field exists in metadata but runtime describe
            # did not expose it.
            # ---------------------------------------------

            else:

                fields.append(
                    metadata_field
                )

                existing_fields_by_name[
                    field_name
                ] = metadata_field

        resolved_name = result.get(
            "name",
            object_name,
        )

        return {
            "name": resolved_name,
            "fullName": resolved_name,

            "label": result.get(
                "label",
                object_name,
            ),

            "fields": fields,

            "relationships": relationships,
        }

    # =====================================================
    # Context Builder
    # =====================================================

    def get_context(
        self,
        objects: list[str],
    ) -> dict:
        """
        Build Salesforce context for selected objects.
        """

        if not isinstance(
            objects,
            list,
        ):
            raise ValueError(
                "Salesforce objects must be provided "
                "as a list."
            )

        object_details = []
        seen_objects = set()

        for object_name in objects:

            if not isinstance(
                object_name,
                str,
            ):
                continue

            object_name = object_name.strip()

            if not object_name:
                continue

            if object_name in seen_objects:
                continue

            seen_objects.add(
                object_name
            )

            object_details.append(
                self.describe_object(
                    object_name
                )
            )

        return {
            "objects": object_details
        }

    # =====================================================
    # Full Context
    # =====================================================

    def get_all_context(
        self,
    ) -> dict:
        """
        Discover Salesforce objects and retrieve metadata
        for every discovered object.

        Avoid using this during normal planning against
        large Salesforce orgs.
        """

        objects = self.list_objects()

        object_names = [
            obj["name"]
            for obj in objects
            if obj.get("name")
        ]

        return self.get_context(
            object_names
        )