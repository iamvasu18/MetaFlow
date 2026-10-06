from Backend.AI.app.services.metadata_spec_store import (
    MetadataSpecStore,
)
from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
)


def build_specification(
    plan_id: str = "PLAN-001",
) -> MetadataSpecification:

    return MetadataSpecification.model_validate(
        {
            "planId": plan_id,
            "metadata": [
                {
                    "itemId": "ITEM-001",
                    "action": "CREATE",
                    "metadataType": "CustomObject",
                    "fullName": "AI_Test_Session__c",
                    "label": "AI Test Session",
                    "description": None,
                    "dependencies": [],
                    "config": {},
                }
            ],
            "validationIssues": [],
        }
    )


def test_save_and_get_specification():

    store = MetadataSpecStore()

    specification = build_specification()

    store.save(
        specification
    )

    result = store.get(
        "PLAN-001"
    )

    assert result is not None
    assert result.planId == "PLAN-001"


def test_get_unknown_specification():

    store = MetadataSpecStore()

    result = store.get(
        "PLAN-NOT-FOUND"
    )

    assert result is None


def test_list_specifications():

    store = MetadataSpecStore()

    store.save(
        build_specification(
            "PLAN-001"
        )
    )

    store.save(
        build_specification(
            "PLAN-002"
        )
    )

    specifications = store.list()

    assert len(specifications) == 2

    plan_ids = {
        specification.planId
        for specification in specifications
    }

    assert plan_ids == {
        "PLAN-001",
        "PLAN-002",
    }


def test_overwrites_existing_plan_specification():

    store = MetadataSpecStore()

    first = build_specification(
        "PLAN-001"
    )

    store.save(
        first
    )

    second = MetadataSpecification.model_validate(
        {
            "planId": "PLAN-001",
            "metadata": [],
            "validationIssues": [],
        }
    )

    store.save(
        second
    )

    result = store.get(
        "PLAN-001"
    )

    assert result is not None
    assert result.metadata == []


def test_delete_specification():

    store = MetadataSpecStore()

    store.save(
        build_specification()
    )

    store.delete(
        "PLAN-001"
    )

    result = store.get(
        "PLAN-001"
    )

    assert result is None