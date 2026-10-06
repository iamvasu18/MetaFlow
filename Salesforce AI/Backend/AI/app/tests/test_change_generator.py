import xml.etree.ElementTree as ET

import pytest

from Backend.AI.app.services.change_generator import (
    SalesforceChangeGenerator,
    SALESFORCE_METADATA_NS,
)
from Backend.AI.app.validators.change_spec_validator import (
    ChangeSpecification,
)


# =========================================================
# Helpers
# =========================================================

NS = {
    "sf": SALESFORCE_METADATA_NS
}


def build_specification(
    metadata_type: str,
    full_name: str,
    changes: dict,
) -> ChangeSpecification:
    """
    Build a valid ChangeSpecification for generator tests.
    """

    dependencies = []

    if metadata_type == "CustomField":
        object_name = full_name.split(
            ".",
            1,
        )[0]

        dependencies = [
            object_name
        ]

    return ChangeSpecification.model_validate(
        {
            "planId": "PLAN-CHANGE-001",
            "changes": [
                {
                    "itemId": "ITEM-001",
                    "action": "UPDATE",
                    "metadataType": (
                        metadata_type
                    ),
                    "fullName": full_name,
                    "dependencies": dependencies,
                    "changes": changes,
                }
            ],
            "validationIssues": [],
        }
    )


def create_object_xml(
    tmp_path,
    object_name: str = "Project__c",
    label: str = "Project",
    plural_label: str = "Projects",
):
    """
    Create a temporary Salesforce CustomObject XML file.
    """

    object_dir = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / object_name
    )

    object_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = (
        object_dir
        / f"{object_name}.object-meta.xml"
    )

    file_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="{SALESFORCE_METADATA_NS}">
    <label>{label}</label>
    <pluralLabel>{plural_label}</pluralLabel>
    <deploymentStatus>Deployed</deploymentStatus>
    <sharingModel>Read</sharingModel>
</CustomObject>
""",
        encoding="utf-8",
    )

    return file_path


def create_text_field_xml(
    tmp_path,
    object_name: str = "Project__c",
    field_name: str = "Name_Text__c",
    label: str = "Name Text",
    required: bool | None = False,
):
    """
    Create a temporary Salesforce Text field XML file.

    required=None means the <required> element is omitted.
    """

    field_dir = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / object_name
        / "fields"
    )

    field_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = (
        field_dir
        / f"{field_name}.field-meta.xml"
    )

    required_xml = ""

    if required is not None:

        required_xml = (
            "\n    <required>"
            + (
                "true"
                if required
                else "false"
            )
            + "</required>"
        )

    file_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="{SALESFORCE_METADATA_NS}">
    <fullName>{field_name}</fullName>
    <label>{label}</label>
    <type>Text</type>{required_xml}
</CustomField>
""",
        encoding="utf-8",
    )

    return file_path


def create_picklist_field_xml(
    tmp_path,
    object_name: str = "AI_Test_Session__c",
    field_name: str = "Status__c",
):
    """
    Create a local Salesforce Picklist field.
    """

    field_dir = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / object_name
        / "fields"
    )

    field_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = (
        field_dir
        / f"{field_name}.field-meta.xml"
    )

    file_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="{SALESFORCE_METADATA_NS}">
    <fullName>{field_name}</fullName>
    <label>Status</label>
    <type>Picklist</type>
    <valueSet>
        <restricted>true</restricted>
        <valueSetDefinition>
            <sorted>false</sorted>
            <value>
                <fullName>Planned</fullName>
                <default>false</default>
                <label>Planned</label>
            </value>
            <value>
                <fullName>Active</fullName>
                <default>false</default>
                <label>Active</label>
            </value>
            <value>
                <fullName>Completed</fullName>
                <default>false</default>
                <label>Completed</label>
            </value>
        </valueSetDefinition>
    </valueSet>
</CustomField>
""",
        encoding="utf-8",
    )

    return file_path


def parse_xml(
    file_path,
):
    return ET.parse(
        file_path
    ).getroot()


# =========================================================
# CustomObject Tests
# =========================================================

def test_update_custom_object_label(
    tmp_path,
):

    file_path = create_object_xml(
        tmp_path
    )

    specification = build_specification(
        metadata_type="CustomObject",
        full_name="Project__c",
        changes={
            "label": {
                "from": "Project",
                "to": "Customer Project",
            }
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    modified_files = generator.apply(
        specification
    )

    root = parse_xml(
        file_path
    )

    label = root.find(
        "sf:label",
        NS,
    )

    assert label is not None

    assert (
        label.text
        == "Customer Project"
    )

    assert len(modified_files) == 1


def test_update_custom_object_plural_label(
    tmp_path,
):

    file_path = create_object_xml(
        tmp_path
    )

    specification = build_specification(
        metadata_type="CustomObject",
        full_name="Project__c",
        changes={
            "pluralLabel": {
                "from": "Projects",
                "to": "Customer Projects",
            }
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    generator.apply(
        specification
    )

    root = parse_xml(
        file_path
    )

    plural_label = root.find(
        "sf:pluralLabel",
        NS,
    )

    assert plural_label is not None

    assert (
        plural_label.text
        == "Customer Projects"
    )


def test_reject_object_label_mismatch(
    tmp_path,
):

    create_object_xml(
        tmp_path,
        label="Project",
    )

    specification = build_specification(
        metadata_type="CustomObject",
        full_name="Project__c",
        changes={
            "label": {
                "from": "Wrong Existing Label",
                "to": "Customer Project",
            }
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    with pytest.raises(
        ValueError,
        match="label mismatch",
    ):

        generator.apply(
            specification
        )


# =========================================================
# CustomField Label Tests
# =========================================================

def test_update_custom_field_label(
    tmp_path,
):

    file_path = create_text_field_xml(
        tmp_path
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "Project__c.Name_Text__c"
        ),
        changes={
            "label": {
                "from": "Name Text",
                "to": "Project Name",
            }
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    generator.apply(
        specification
    )

    root = parse_xml(
        file_path
    )

    label = root.find(
        "sf:label",
        NS,
    )

    assert label is not None

    assert (
        label.text
        == "Project Name"
    )


# =========================================================
# Required Field Tests
# =========================================================

def test_update_required_false_to_true(
    tmp_path,
):

    file_path = create_text_field_xml(
        tmp_path,
        required=False,
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "Project__c.Name_Text__c"
        ),
        changes={
            "required": {
                "from": False,
                "to": True,
            }
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    generator.apply(
        specification
    )

    root = parse_xml(
        file_path
    )

    required = root.find(
        "sf:required",
        NS,
    )

    assert required is not None
    assert required.text == "true"


def test_update_required_when_element_missing(
    tmp_path,
):

    file_path = create_text_field_xml(
        tmp_path,
        required=None,
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "Project__c.Name_Text__c"
        ),
        changes={
            "required": {
                "from": False,
                "to": True,
            }
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    generator.apply(
        specification
    )

    root = parse_xml(
        file_path
    )

    required = root.find(
        "sf:required",
        NS,
    )

    assert required is not None
    assert required.text == "true"


def test_reject_required_mismatch(
    tmp_path,
):

    create_text_field_xml(
        tmp_path,
        required=True,
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "Project__c.Name_Text__c"
        ),
        changes={
            "required": {
                "from": False,
                "to": True,
            }
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    with pytest.raises(
        ValueError,
        match="required mismatch",
    ):

        generator.apply(
            specification
        )


# =========================================================
# Picklist Tests
# =========================================================

def test_add_picklist_value(
    tmp_path,
):

    file_path = create_picklist_field_xml(
        tmp_path
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "AI_Test_Session__c."
            "Status__c"
        ),
        changes={
            "addPicklistValues": [
                "Cancelled"
            ]
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    modified_files = generator.apply(
        specification
    )

    root = parse_xml(
        file_path
    )

    values = []

    for value_element in root.findall(
        ".//sf:value",
        NS,
    ):

        full_name = value_element.find(
            "sf:fullName",
            NS,
        )

        if (
            full_name is not None
            and full_name.text
        ):
            values.append(
                full_name.text
            )

    assert values == [
        "Planned",
        "Active",
        "Completed",
        "Cancelled",
    ]

    assert len(modified_files) == 1


def test_add_picklist_value_namespaced_metadata(
    tmp_path,
):
    """
    Verify that the change generator supports
    namespaced Salesforce object and field API names.
    """

    object_name = (
        "LayaDevHub__AI_Test_Session__c"
    )

    field_name = (
        "LayaDevHub__Status__c"
    )

    file_path = create_picklist_field_xml(
        tmp_path,
        object_name=object_name,
        field_name=field_name,
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "LayaDevHub__AI_Test_Session__c."
            "LayaDevHub__Status__c"
        ),
        changes={
            "addPicklistValues": [
                "Cancelled"
            ]
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    modified_files = generator.apply(
        specification
    )

    root = parse_xml(
        file_path
    )

    values = []

    for value_element in root.findall(
        ".//sf:value",
        NS,
    ):

        full_name = value_element.find(
            "sf:fullName",
            NS,
        )

        if (
            full_name is not None
            and full_name.text
        ):
            values.append(
                full_name.text
            )

    assert values == [
        "Planned",
        "Active",
        "Completed",
        "Cancelled",
    ]
    assert (
    modified_files[0]
    == str(
        file_path.relative_to(
            tmp_path
        )
    )
)

def test_add_multiple_picklist_values(
    tmp_path,
):

    file_path = create_picklist_field_xml(
        tmp_path
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "AI_Test_Session__c."
            "Status__c"
        ),
        changes={
            "addPicklistValues": [
                "Cancelled",
                "Paused",
            ]
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    generator.apply(
        specification
    )

    root = parse_xml(
        file_path
    )

    values = [
        element.text
        for element in root.findall(
            ".//sf:value/sf:fullName",
            NS,
        )
    ]

    assert "Cancelled" in values
    assert "Paused" in values


def test_reject_existing_picklist_value(
    tmp_path,
):

    create_picklist_field_xml(
        tmp_path
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "AI_Test_Session__c."
            "Status__c"
        ),
        changes={
            "addPicklistValues": [
                "Active"
            ]
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):

        generator.apply(
            specification
        )


def test_reject_picklist_change_on_text_field(
    tmp_path,
):

    create_text_field_xml(
        tmp_path,
        object_name="Project__c",
        field_name="Status__c",
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "Project__c.Status__c"
        ),
        changes={
            "addPicklistValues": [
                "Cancelled"
            ]
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    with pytest.raises(
        ValueError,
        match="not a Picklist field",
    ):

        generator.apply(
            specification
        )


# =========================================================
# Global Value Set Safety Test
# =========================================================

def test_reject_global_value_set(
    tmp_path,
):

    field_dir = (
        tmp_path
        / "force-app"
        / "main"
        / "default"
        / "objects"
        / "Project__c"
        / "fields"
    )

    field_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = (
        field_dir
        / "Status__c.field-meta.xml"
    )

    file_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="{SALESFORCE_METADATA_NS}">
    <fullName>Status__c</fullName>
    <label>Status</label>
    <type>Picklist</type>
    <valueSet>
        <valueSetName>Project_Status</valueSetName>
    </valueSet>
</CustomField>
""",
        encoding="utf-8",
    )

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "Project__c.Status__c"
        ),
        changes={
            "addPicklistValues": [
                "Cancelled"
            ]
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    with pytest.raises(
        ValueError,
        match="Global Value Set",
    ):

        generator.apply(
            specification
        )


# =========================================================
# Missing File Test
# =========================================================

def test_reject_missing_metadata_file(
    tmp_path,
):

    specification = build_specification(
        metadata_type="CustomField",
        full_name=(
            "Missing__c.Status__c"
        ),
        changes={
            "label": {
                "from": "Status",
                "to": "New Status",
            }
        },
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    with pytest.raises(
        FileNotFoundError,
        match="metadata file not found",
    ):

        generator.apply(
            specification
        )


# =========================================================
# Validation Issue Safety Test
# =========================================================

def test_reject_specification_with_validation_issues(
    tmp_path,
):

    specification = (
        ChangeSpecification.model_validate(
            {
                "planId": "PLAN-CHANGE-001",
                "changes": [],
                "validationIssues": [
                    {
                        "code": (
                            "METADATA_NOT_FOUND"
                        ),
                        "itemId": "ITEM-001",
                        "message": (
                            "Existing Salesforce metadata "
                            "could not be found."
                        ),
                    }
                ],
            }
        )
    )

    generator = SalesforceChangeGenerator(
        project_root=tmp_path
    )

    with pytest.raises(
        ValueError,
        match="validation issues",
    ):

        generator.apply(
            specification
        )