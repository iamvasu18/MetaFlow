from Backend.AI.app.salesforce.metadata_service import (
    SalesforceMetadataService,
)


def test_describe_object_parses_fields(
    monkeypatch,
):

    service = SalesforceMetadataService(
        target_org="test-org"
    )

    monkeypatch.setattr(
        service,
        "_run_sf_command",
        lambda command: {
            "result": {
                "name": "Account",
                "label": "Account",
                "fields": [
                    {
                        "name": "Name",
                        "label": "Account Name",
                        "type": "string",
                        "nillable": False,
                    },
                    {
                        "name": "Industry",
                        "label": "Industry",
                        "type": "picklist",
                        "nillable": True,
                    },
                ],
            }
        },
    )

    result = service.describe_object(
        "Account"
    )

    assert result["name"] == "Account"
    assert result["label"] == "Account"

    assert len(
        result["fields"]
    ) == 2

    assert (
        result["fields"][0]["name"]
        == "Name"
    )

    assert (
        result["fields"][0]["required"]
        is True
    )

    assert (
        result["fields"][1]["required"]
        is False
    )

    assert result["relationships"] == []


def test_describe_object_parses_relationships(
    monkeypatch,
):

    service = SalesforceMetadataService(
        target_org="test-org"
    )

    monkeypatch.setattr(
        service,
        "_run_sf_command",
        lambda command: {
            "result": {
                "name": "Contact",
                "label": "Contact",
                "fields": [
                    {
                        "name": "LastName",
                        "label": "Last Name",
                        "type": "string",
                        "nillable": False,
                    },
                    {
                        "name": "AccountId",
                        "label": "Account ID",
                        "type": "reference",
                        "nillable": True,
                        "referenceTo": [
                            "Account"
                        ],
                        "relationshipName": (
                            "Account"
                        ),
                    },
                ],
            }
        },
    )

    result = service.describe_object(
        "Contact"
    )

    assert len(
        result["relationships"]
    ) == 1

    relationship = (
        result["relationships"][0]
    )

    assert (
        relationship["field"]
        == "AccountId"
    )

    assert (
        relationship["type"]
        == "reference"
    )

    assert (
        relationship["referenceTo"]
        == ["Account"]
    )

    assert (
        relationship["relationshipName"]
        == "Account"
    )

    account_field = (
        result["fields"][1]
    )

    assert (
        account_field["referenceTo"]
        == ["Account"]
    )

    assert (
        account_field["relationshipName"]
        == "Account"
    )


def test_get_context_builds_object_context(
    monkeypatch,
):

    service = SalesforceMetadataService(
        target_org="test-org"
    )

    def fake_describe(
        object_name,
    ):

        return {
            "name": object_name,
            "label": object_name,
            "fields": [],
            "relationships": [],
        }

    monkeypatch.setattr(
        service,
        "describe_object",
        fake_describe,
    )

    result = service.get_context(
        [
            "Account",
            "Contact",
        ]
    )

    assert result == {
        "objects": [
            {
                "name": "Account",
                "label": "Account",
                "fields": [],
                "relationships": [],
            },
            {
                "name": "Contact",
                "label": "Contact",
                "fields": [],
                "relationships": [],
            },
        ]
    }


def test_list_objects_parses_cli_response(
    monkeypatch,
):

    service = SalesforceMetadataService(
        target_org="test-org"
    )

    monkeypatch.setattr(
        service,
        "_run_sf_command",
        lambda command: {
            "result": [
                "Account",
                "Contact",
                {
                    "name": "Opportunity",
                    "label": "Opportunity",
                },
            ]
        },
    )

    result = service.list_objects()

    assert result == [
        {
            "name": "Account",
            "fullName": "Account",
            "label": None,
        },
        {
            "name": "Contact",
            "fullName": "Contact",
            "label": None,
        },
        {
            "name": "Opportunity",
            "fullName": "Opportunity",
            "label": "Opportunity",
        },
    ]

def test_find_relevant_objects(
    monkeypatch,
):

    service = SalesforceMetadataService(
        target_org="test-org"
    )

    monkeypatch.setattr(
        service,
        "list_objects",
        lambda: [
            {
                "name": "Account",
                "label": "Account",
            },
            {
                "name": "Contact",
                "label": "Contact",
            },
            {
                "name": "Opportunity",
                "label": "Opportunity",
            },
        ],
    )

    result = service.find_relevant_objects(
        requirement="Create a Contact",
    )

    assert result == [
        "Contact"
    ]