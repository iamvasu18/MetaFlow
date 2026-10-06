from Backend.AI.app.providers.mock_provider import (
    MockProvider,
)
from Backend.AI.app.services.planning_service import (
    PlanningService,
)


def test_planning_service_generates_plan():

    provider = MockProvider()

    service = PlanningService(
        provider=provider
    )

    requirement = (
        "Create an Appointment custom object "
        "with Appointment Date and Status fields."
    )

    salesforce_context = {
        "objects": [
            {
                "name": "Account"
            },
            {
                "name": "Contact"
            }
        ]
    }

    plan = service.generate_plan(
        requirement=requirement,
        salesforce_context=salesforce_context,
    )

    assert plan.id == "PLAN-MOCK-001"

    assert (
        plan.requirementId
        == "REQ-MOCK-001"
    )

    assert plan.status == "DRAFT"

    assert len(plan.items) == 3


def test_planning_service_returns_salesforce_metadata():

    service = PlanningService(
        provider=MockProvider()
    )

    plan = service.generate_plan(
        requirement=(
            "Create an Appointment object."
        ),
        salesforce_context={
            "objects": []
        },
    )

    metadata_types = [
        item.metadataType
        for item in plan.items
    ]

    assert "CustomObject" in metadata_types
    assert "CustomField" in metadata_types


def test_planning_service_preserves_dependencies():

    service = PlanningService(
        provider=MockProvider()
    )

    plan = service.generate_plan(
        requirement=(
            "Create an Appointment object."
        ),
        salesforce_context={
            "objects": []
        },
    )

    object_item = plan.items[0]
    date_field = plan.items[1]
    status_field = plan.items[2]

    assert object_item.dependencies == []

    assert (
        "ITEM-001"
        in date_field.dependencies
    )

    assert (
        "ITEM-001"
        in status_field.dependencies
    )


def test_planning_service_discovers_relevant_objects():

    provider = MockProvider()

    class FakeMetadataService:

        def find_relevant_objects(
            self,
            requirement,
        ):
            return [
                "Contact"
            ]

        def get_context(
            self,
            objects,
        ):
            assert objects == [
                "Contact"
            ]

            return {
                "objects": [
                    {
                        "name": "Contact",
                        "label": "Contact",
                        "fields": [
                            {
                                "name": "Email",
                                "label": "Email",
                                "type": "email",
                                "required": False,
                            }
                        ],
                    }
                ]
            }

    service = PlanningService(
        provider=provider,
        metadata_service=FakeMetadataService(),
    )

    result = service.generate_plan(
        requirement=(
            "Create a Contact with an Email field."
        )
    )

    assert result is not None


def test_planning_service_handles_no_matching_objects():

    provider = MockProvider()

    class FakeMetadataService:

        def find_relevant_objects(
            self,
            requirement,
        ):
            return []

        def get_context(
            self,
            objects,
        ):
            raise AssertionError(
                "get_context should not be called "
                "when there are no matching objects."
            )

    service = PlanningService(
        provider=provider,
        metadata_service=FakeMetadataService(),
    )

    result = service.generate_plan(
        requirement="Create a spaceship."
    )

    assert result is not None


def test_planning_service_includes_salesforce_context_in_prompt():

    class RecordingProvider:

        def __init__(self):
            self.user_prompt = None

        def generate(
            self,
            system_prompt,
            user_prompt,
        ):
            self.user_prompt = user_prompt

            return (
                '{"id":"PLAN-CONTEXT-001",'
                '"requirementId":"REQ-CONTEXT-001",'
                '"summary":"Context test",'
                '"assumptions":[],"items":[],'
                '"storyPoints":1,"status":"DRAFT"}'
            )

    provider = RecordingProvider()

    service = PlanningService(
        provider=provider
    )

    salesforce_context = {
        "objects": [
            {
                "name": "Contact",
                "label": "Contact",
                "fields": [
                    {
                        "name": "Email",
                        "label": "Email",
                        "type": "email",
                        "required": False,
                    }
                ],
            }
        ]
    }

    service.generate_plan(
        requirement=(
            "Create a Contact with an Email field."
        ),
        salesforce_context=salesforce_context,
    )

    assert provider.user_prompt is not None

    assert "Contact" in provider.user_prompt

    assert "Email" in provider.user_prompt