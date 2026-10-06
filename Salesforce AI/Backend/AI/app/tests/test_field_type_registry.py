import pytest

from Backend.AI.app.services.field_type_registry import (
    SalesforceFieldTypeRegistry,
)


@pytest.mark.parametrize(
    (
        "input_type",
        "expected",
    ),
    [
        ("Text", "Text"),
        ("text", "Text"),

        ("Text Area", "TextArea"),
        ("textarea", "TextArea"),

        ("Long Text Area", "LongTextArea"),

        ("Rich Text", "Html"),
        ("Rich Text Area", "Html"),

        ("Encrypted Text", "EncryptedText"),

        ("Number", "Number"),
        ("Currency", "Currency"),
        ("Percent", "Percent"),

        ("Date", "Date"),
        ("Date/Time", "DateTime"),
        ("Date Time", "DateTime"),
        ("Time", "Time"),

        ("Checkbox", "Checkbox"),
        ("Boolean", "Checkbox"),

        ("Picklist", "Picklist"),

        (
            "Multi-Select Picklist",
            "MultiselectPicklist",
        ),

        ("Email", "Email"),
        ("Phone", "Phone"),
        ("URL", "Url"),

        ("Lookup", "Lookup"),
        ("Master-Detail", "MasterDetail"),

        ("Geolocation", "Location"),

        ("Auto Number", "AutoNumber"),

        ("Formula", "Formula"),

        ("Roll-Up Summary", "Summary"),
    ],
)
def test_normalize_field_types(
    input_type,
    expected,
):

    assert (
        SalesforceFieldTypeRegistry
        .normalize(
            input_type
        )
        == expected
    )


def test_reject_unknown_type():

    with pytest.raises(
        ValueError,
        match=(
            "Unsupported Salesforce field type"
        ),
    ):

        SalesforceFieldTypeRegistry.normalize(
            "RandomFieldType"
        )


def test_supported_types_contains_core_types():

    supported = (
        SalesforceFieldTypeRegistry
        .supported_types()
    )

    assert "Text" in supported
    assert "Currency" in supported
    assert "Lookup" in supported
    assert "Formula" in supported
    assert "Summary" in supported