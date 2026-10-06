import json

from Backend.AI.app.providers.mock_provider import (
    MockProvider,
)


def test_mock_provider_returns_response():

    provider = MockProvider()

    response = provider.generate(
        system_prompt="Test system prompt",
        user_prompt="Create an Appointment object.",
    )

    assert response
    assert isinstance(response, str)


def test_mock_provider_returns_valid_json():

    provider = MockProvider()

    response = provider.generate(
        system_prompt="Test system prompt",
        user_prompt="Create an Appointment object.",
    )

    data = json.loads(response)

    assert data["id"] == "PLAN-MOCK-001"
    assert data["status"] == "DRAFT"
    assert len(data["items"]) == 3


def test_mock_provider_returns_salesforce_plan():

    provider = MockProvider()

    response = provider.generate(
        system_prompt="Test system prompt",
        user_prompt="Create an Appointment object.",
    )

    data = json.loads(response)

    metadata_types = [
        item["metadataType"]
        for item in data["items"]
    ]

    assert "CustomObject" in metadata_types
    assert "CustomField" in metadata_types


def test_mock_provider_contact_existing_metadata_returns_no_change():

    provider = MockProvider()

    user_prompt = """
Create a Contact with First Name, Last Name and Email.

<SALESFORCE_CONTEXT>
{
    "objects": [
        {
            "name": "Contact",
            "label": "Contact",
            "fields": [
                {
                    "name": "FirstName",
                    "label": "First Name",
                    "type": "string",
                    "required": false
                },
                {
                    "name": "LastName",
                    "label": "Last Name",
                    "type": "string",
                    "required": true
                },
                {
                    "name": "Email",
                    "label": "Email",
                    "type": "email",
                    "required": false
                }
            ]
        }
    ]
}
</SALESFORCE_CONTEXT>
"""

    response = provider.generate(
        system_prompt="Test system prompt",
        user_prompt=user_prompt,
    )

    data = json.loads(response)

    assert data["id"] == (
        "PLAN-MOCK-CONTACT-001"
    )

    assert len(data["items"]) == 4

    actions = {
        item["fullName"]: item["action"]
        for item in data["items"]
    }

    assert actions["Contact"] == "NO_CHANGE"

    assert (
        actions["Contact.FirstName"]
        == "NO_CHANGE"
    )

    assert (
        actions["Contact.LastName"]
        == "NO_CHANGE"
    )

    assert (
        actions["Contact.Email"]
        == "NO_CHANGE"
    )


def test_mock_provider_contact_missing_email_creates_email():

    provider = MockProvider()

    user_prompt = """
Create a Contact with First Name, Last Name and Email.

<SALESFORCE_CONTEXT>
{
    "objects": [
        {
            "name": "Contact",
            "label": "Contact",
            "fields": [
                {
                    "name": "FirstName",
                    "label": "First Name",
                    "type": "string",
                    "required": false
                },
                {
                    "name": "LastName",
                    "label": "Last Name",
                    "type": "string",
                    "required": true
                }
            ]
        }
    ]
}
</SALESFORCE_CONTEXT>
"""

    response = provider.generate(
        system_prompt="Test system prompt",
        user_prompt=user_prompt,
    )

    data = json.loads(response)

    actions = {
        item["fullName"]: item["action"]
        for item in data["items"]
    }

    assert actions["Contact"] == "NO_CHANGE"

    assert (
        actions["Contact.FirstName"]
        == "NO_CHANGE"
    )

    assert (
        actions["Contact.LastName"]
        == "NO_CHANGE"
    )

    assert (
        actions["Contact.Email"]
        == "CREATE"
    )


def test_mock_provider_contact_missing_object_creates_contact():

    provider = MockProvider()

    user_prompt = """
Create a Contact with First Name, Last Name and Email.

<SALESFORCE_CONTEXT>
{
    "objects": [
        {
            "name": "Account",
            "label": "Account",
            "fields": []
        }
    ]
}
</SALESFORCE_CONTEXT>
"""

    response = provider.generate(
        system_prompt="Test system prompt",
        user_prompt=user_prompt,
    )

    data = json.loads(response)

    actions = {
        item["fullName"]: item["action"]
        for item in data["items"]
    }

    assert actions["Contact"] == "CREATE"

    assert (
        actions["Contact.FirstName"]
        == "CREATE"
    )

    assert (
        actions["Contact.LastName"]
        == "CREATE"
    )

    assert (
        actions["Contact.Email"]
        == "CREATE"
    )


def test_mock_provider_training_session_still_works():

    provider = MockProvider()

    response = provider.generate(
        system_prompt="Test system prompt",
        user_prompt=(
            "Create a Training Session custom "
            "object with Session Date and Status fields."
        ),
    )

    data = json.loads(response)

    assert data["id"] == (
        "PLAN-MOCK-TRAINING-001"
    )

    assert data["status"] == "DRAFT"

    assert len(data["items"]) == 3