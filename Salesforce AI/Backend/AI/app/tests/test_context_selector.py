from Backend.AI.app.salesforce.context_selector import (
    SalesforceContextSelector,
)


def test_selector_returns_matching_object():

    selector = SalesforceContextSelector()

    metadata = {
        "objects": [
            {
                "name": "Account",
                "label": "Account",
                "fields": [],
            },
            {
                "name": "Contact",
                "label": "Contact",
                "fields": [],
            },
        ]
    }

    result = selector.select(
        requirement="Create a Contact record.",
        metadata=metadata,
    )

    object_names = [
        obj["name"]
        for obj in result["objects"]
    ]

    assert "Contact" in object_names


def test_selector_uses_field_information():

    selector = SalesforceContextSelector()

    metadata = {
        "objects": [
            {
                "name": "Account",
                "label": "Account",
                "fields": [
                    {
                        "name": "Industry",
                        "label": "Industry",
                    }
                ],
            },
            {
                "name": "Contact",
                "label": "Contact",
                "fields": [],
            },
        ]
    }

    result = selector.select(
        requirement="Use the Industry field.",
        metadata=metadata,
    )

    assert (
        result["objects"][0]["name"]
        == "Account"
    )


def test_selector_respects_max_objects():

    selector = SalesforceContextSelector(
        max_objects=2
    )

    metadata = {
        "objects": [
            {
                "name": "Account",
                "label": "Account",
                "fields": [],
            },
            {
                "name": "Contact",
                "label": "Contact",
                "fields": [],
            },
            {
                "name": "Lead",
                "label": "Lead",
                "fields": [],
            },
        ]
    }

    result = selector.select(
        requirement=(
            "Create an Account Contact Lead"
        ),
        metadata=metadata,
    )

    assert len(
        result["objects"]
    ) <= 2


def test_selector_returns_empty_context_when_no_match():

    selector = SalesforceContextSelector()

    metadata = {
        "objects": [
            {
                "name": "Account",
                "label": "Account",
                "fields": [],
            }
        ]
    }

    result = selector.select(
        requirement="Create a spaceship.",
        metadata=metadata,
    )

    assert result == {
        "objects": []
    }