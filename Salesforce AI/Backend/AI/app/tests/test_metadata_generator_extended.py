from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from Backend.AI.app.services.metadata_generator import (
    SalesforceMetadataGenerator,
)
from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
)


# =========================================================
# Helpers
# =========================================================


def build_spec(item: dict) -> MetadataSpecification:
    """
    Build one validated MetadataSpecification for a single
    CREATE component.
    """

    return MetadataSpecification.model_validate(
        {
            "planId": "PLAN-EXTENDED-001",
            "metadata": [
                item
            ],
            "validationIssues": [],
        }
    )


def generate_single(
    tmp_path,
    item: dict,
) -> tuple[Path, str]:
    """
    Generate one metadata file and return:
    - generated Path
    - file content
    """

    specification = build_spec(
        item
    )

    generator = SalesforceMetadataGenerator(
        project_root=str(
            tmp_path
        )
    )

    generated_files = (
        generator.generate_from_specification(
            specification
        )
    )

    assert len(
        generated_files
    ) == 1

    file_path = Path(
        generated_files[0]
    )

    assert file_path.exists()

    content = file_path.read_text(
        encoding="utf-8"
    )

    # Every generated file in these tests should be
    # well-formed XML.
    ET.fromstring(
        content
    )

    return (
        file_path,
        content,
    )


def custom_field_item(
    *,
    full_name: str,
    label: str,
    config: dict,
) -> dict:
    return {
        "itemId": "ITEM-001",
        "action": "CREATE",
        "metadataType": "CustomField",
        "fullName": full_name,
        "label": label,
        "description": None,
        "dependencies": [],
        "config": config,
    }


# =========================================================
# Simple field families
# =========================================================


@pytest.mark.parametrize(
    (
        "field_type",
        "field_name",
    ),
    [
        (
            "Phone",
            "Phone_Number__c",
        ),
        (
            "Url",
            "Website__c",
        ),
        (
            "DateTime",
            "Event_Time__c",
        ),
        (
            "Time",
            "Start_Time__c",
        ),
    ],
)
def test_generates_simple_extended_field_types(
    tmp_path,
    field_type,
    field_name,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Extended_Test__c."
                f"{field_name}"
            ),
            label=field_type,
            config={
                "type": field_type,
                "required": False,
            },
        ),
    )

    assert (
        f"<type>{field_type}</type>"
        in content
    )

    assert (
        "<required>false</required>"
        in content
    )


# =========================================================
# Checkbox
# =========================================================


def test_generates_checkbox_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Extended_Test__c."
                "Is_Active__c"
            ),
            label="Is Active",
            config={
                "type": "Checkbox",
                "defaultValue": True,
            },
        ),
    )

    assert (
        "<type>Checkbox</type>"
        in content
    )

    assert (
        "<defaultValue>true</defaultValue>"
        in content
    )


# =========================================================
# Number / Currency / Percent
# =========================================================


@pytest.mark.parametrize(
    "field_type",
    [
        "Number",
        "Currency",
        "Percent",
    ],
)
def test_generates_numeric_field_types(
    tmp_path,
    field_type,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Extended_Test__c."
                f"{field_type}_Value__c"
            ),
            label=(
                f"{field_type} Value"
            ),
            config={
                "type": field_type,
                "precision": 18,
                "scale": 2,
                "required": False,
            },
        ),
    )

    assert (
        f"<type>{field_type}</type>"
        in content
    )

    assert (
        "<precision>18</precision>"
        in content
    )

    assert (
        "<scale>2</scale>"
        in content
    )


def test_rejects_numeric_scale_above_precision():
    item = custom_field_item(
        full_name=(
            "Extended_Test__c."
            "Bad_Number__c"
        ),
        label="Bad Number",
        config={
            "type": "Number",
            "precision": 5,
            "scale": 6,
            "required": False,
        },
    )

    with pytest.raises(
        ValueError,
        match=(
            "scale must not exceed precision"
        ),
    ):
        build_spec(
            item
        )


# =========================================================
# Multi-Select Picklist
# =========================================================


def test_generates_multiselect_picklist(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Extended_Test__c."
                "Skills__c"
            ),
            label="Skills",
            config={
                "type": (
                    "MultiselectPicklist"
                ),
                "values": [
                    "Apex",
                    "LWC",
                    "Flow",
                ],
                "visibleLines": 5,
            },
        ),
    )

    assert (
        "<type>MultiselectPicklist</type>"
        in content
    )

    assert (
        "<visibleLines>5</visibleLines>"
        in content
    )

    assert (
        "<fullName>Apex</fullName>"
        in content
    )

    assert (
        "<fullName>LWC</fullName>"
        in content
    )

    assert (
        "<fullName>Flow</fullName>"
        in content
    )


# =========================================================
# Location
# =========================================================


def test_generates_location_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Extended_Test__c."
                "Office_Location__c"
            ),
            label="Office Location",
            config={
                "type": "Location",
                "scale": 5,
                "displayLocationInDecimal": True,
                "required": False,
            },
        ),
    )

    assert (
        "<type>Location</type>"
        in content
    )

    assert (
        "<scale>5</scale>"
        in content
    )

    assert (
        "<displayLocationInDecimal>"
        "true"
        "</displayLocationInDecimal>"
        in content
    )


# =========================================================
# Lookup
# =========================================================


def test_generates_lookup_field(
    tmp_path,
):
    file_path, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Field_List__c."
                "Developer__c"
            ),
            label="Developer",
            config={
                "type": "Lookup",
                "referenceTo": "Account",
                "relationshipName": (
                    "Field_List_Developers"
                ),
                "deleteConstraint": (
                    "SetNull"
                ),
                "required": False,
            },
        ),
    )

    assert (
        file_path.name
        == "Developer__c.field-meta.xml"
    )

    assert (
        "<type>Lookup</type>"
        in content
    )

    assert (
        "<referenceTo>Account</referenceTo>"
        in content
    )

    assert (
        "<relationshipName>"
        "Field_List_Developers"
        "</relationshipName>"
        in content
    )

    assert (
        "<deleteConstraint>"
        "SetNull"
        "</deleteConstraint>"
        in content
    )


# =========================================================
# Master-Detail
# =========================================================


def test_generates_master_detail_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Invoice_Line__c."
                "Invoice__c"
            ),
            label="Invoice",
            config={
                "type": "MasterDetail",
                "referenceTo": "Invoice__c",
                "relationshipName": (
                    "Invoice_Lines"
                ),
                "reparentableMasterDetail": (
                    False
                ),
                "writeRequiresMasterRead": (
                    False
                ),
            },
        ),
    )

    assert (
        "<type>MasterDetail</type>"
        in content
    )

    assert (
        "<referenceTo>Invoice__c</referenceTo>"
        in content
    )

    assert (
        "<relationshipName>"
        "Invoice_Lines"
        "</relationshipName>"
        in content
    )

    assert (
        "<reparentableMasterDetail>"
        "false"
        "</reparentableMasterDetail>"
        in content
    )

    assert (
        "<writeRequiresMasterRead>"
        "false"
        "</writeRequiresMasterRead>"
        in content
    )


# =========================================================
# External Lookup
# =========================================================


def test_generates_external_lookup_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "External_Order__x."
                "Customer__c"
            ),
            label="Customer",
            config={
                "type": "ExternalLookup",
                "referenceTo": "Account",
                "relationshipName": (
                    "External_Orders"
                ),
                "required": False,
            },
        ),
    )

    assert (
        "<type>ExternalLookup</type>"
        in content
    )

    assert (
        "<referenceTo>Account</referenceTo>"
        in content
    )

    assert (
        "<relationshipName>"
        "External_Orders"
        "</relationshipName>"
        in content
    )


# =========================================================
# Auto Number
# =========================================================


def test_generates_auto_number_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Extended_Test__c."
                "Reference_Number__c"
            ),
            label="Reference Number",
            config={
                "type": "AutoNumber",
                "displayFormat": (
                    "REF-{0000}"
                ),
                "startingNumber": 1,
            },
        ),
    )

    assert (
        "<type>AutoNumber</type>"
        in content
    )

    assert (
        "<displayFormat>"
        "REF-{0000}"
        "</displayFormat>"
        in content
    )

    assert (
        "<startingNumber>1</startingNumber>"
        in content
    )


# =========================================================
# Formula
# =========================================================


def test_generates_number_formula_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Extended_Test__c."
                "Total_With_Tax__c"
            ),
            label="Total With Tax",
            config={
                "type": "Formula",
                "formula": (
                    "Amount__c * 1.18"
                ),
                "formulaReturnType": (
                    "Currency"
                ),
                "precision": 18,
                "scale": 2,
            },
        ),
    )

    assert (
        "<type>Currency</type>"
        in content
    )

    assert (
        "<type>Formula</type>"
        not in content
    )

    assert (
        "<formula><![CDATA["
        "Amount__c * 1.18"
        "]]></formula>"
        in content
    )

    assert (
        "<precision>18</precision>"
        in content
    )

    assert (
        "<scale>2</scale>"
        in content
    )

    assert (
        "<formulaTreatBlanksAs>"
        "BlankAsZero"
        "</formulaTreatBlanksAs>"
        in content
    )


def test_generates_text_formula_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Extended_Test__c."
                "Display_Name__c"
            ),
            label="Display Name",
            config={
                "type": "Formula",
                "formula": (
                    'Name & " - Test"'
                ),
                "formulaReturnType": (
                    "Text"
                ),
            },
        ),
    )

    assert (
        "<type>Text</type>"
        in content
    )

    assert (
        "<formulaTreatBlanksAs>"
        "BlankAsBlank"
        "</formulaTreatBlanksAs>"
        in content
    )


# =========================================================
# Roll-Up Summary
# =========================================================


def test_generates_summary_sum_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Invoice__c."
                "Total_Line_Amount__c"
            ),
            label="Total Line Amount",
            config={
                "type": "Summary",
                "summaryForeignKey": (
                    "Invoice_Line__c.Invoice__c"
                ),
                "summaryOperation": "Sum",
                "summarizedField": (
                    "Invoice_Line__c.Amount__c"
                ),
            },
        ),
    )

    assert (
        "<type>Summary</type>"
        in content
    )

    assert (
        "<summaryForeignKey>"
        "Invoice_Line__c.Invoice__c"
        "</summaryForeignKey>"
        in content
    )

    assert (
        "<summaryOperation>sum</summaryOperation>"
        in content
    )

    assert (
        "<summarizedField>"
        "Invoice_Line__c.Amount__c"
        "</summarizedField>"
        in content
    )


def test_generates_summary_count_without_summarized_field(
    tmp_path,
):
    _, content = generate_single(
        tmp_path,
        custom_field_item(
            full_name=(
                "Invoice__c."
                "Line_Count__c"
            ),
            label="Line Count",
            config={
                "type": "Summary",
                "summaryForeignKey": (
                    "Invoice_Line__c.Invoice__c"
                ),
                "summaryOperation": "Count",
            },
        ),
    )

    assert (
        "<summaryOperation>"
        "count"
        "</summaryOperation>"
        in content
    )

    assert (
        "<summarizedField>"
        not in content
    )


# =========================================================
# Validation Rule
# =========================================================


def test_generates_validation_rule(
    tmp_path,
):
    file_path, content = generate_single(
        tmp_path,
        {
            "itemId": "ITEM-001",
            "action": "CREATE",
            "metadataType": (
                "ValidationRule"
            ),
            "fullName": (
                "Field_List__c."
                "Require_Developer"
            ),
            "label": (
                "Require Developer"
            ),
            "description": (
                "Require Developer before save."
            ),
            "dependencies": [],
            "config": {
                "active": True,
                "errorConditionFormula": (
                    "ISBLANK(Developer__c)"
                ),
                "errorMessage": (
                    "Developer is required."
                ),
                "errorDisplayField": (
                    "Developer__c"
                ),
            },
        },
    )

    assert (
        file_path.name
        == (
            "Require_Developer"
            ".validationRule-meta.xml"
        )
    )

    assert (
        "validationRules"
        in file_path.parts
    )

    assert (
        "<fullName>"
        "Require_Developer"
        "</fullName>"
        in content
    )

    assert (
        "<active>true</active>"
        in content
    )

    assert (
        "<errorConditionFormula>"
        "<![CDATA["
        "ISBLANK(Developer__c)"
        "]]>"
        "</errorConditionFormula>"
        in content
    )

    assert (
        "<errorDisplayField>"
        "Developer__c"
        "</errorDisplayField>"
        in content
    )

    assert (
        "<errorMessage>"
        "Developer is required."
        "</errorMessage>"
        in content
    )


# =========================================================
# Specification-level validation
# =========================================================


def test_validation_rule_requires_formula():
    item = {
        "itemId": "ITEM-001",
        "action": "CREATE",
        "metadataType": "ValidationRule",
        "fullName": (
            "Extended_Test__c."
            "Bad_Rule"
        ),
        "label": "Bad Rule",
        "description": None,
        "dependencies": [],
        "config": {
            "active": True,
            "errorMessage": (
                "Value is required."
            ),
        },
    }

    with pytest.raises(
        ValueError,
        match=(
            "errorConditionFormula"
        ),
    ):
        build_spec(
            item
        )


def test_lookup_requires_reference_to():
    item = custom_field_item(
        full_name=(
            "Extended_Test__c."
            "Missing_Reference__c"
        ),
        label="Missing Reference",
        config={
            "type": "Lookup",
            "relationshipName": (
                "Missing_References"
            ),
            "required": False,
        },
    )

    with pytest.raises(
        ValueError,
        match="referenceTo",
    ):
        build_spec(
            item
        )


def test_multiselect_requires_visible_lines():
    item = custom_field_item(
        full_name=(
            "Extended_Test__c."
            "Missing_Lines__c"
        ),
        label="Missing Lines",
        config={
            "type": (
                "MultiselectPicklist"
            ),
            "values": [
                "One",
                "Two",
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="visibleLines",
    ):
        build_spec(
            item
        )
