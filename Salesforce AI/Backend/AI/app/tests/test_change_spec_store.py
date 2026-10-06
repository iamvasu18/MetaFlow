from Backend.AI.app.services.change_spec_store import (
    ChangeSpecStore,
)

from Backend.AI.app.validators.change_spec_validator import (
    ChangeSpecification,
)


def build_specification(
    plan_id: str = "PLAN-CHANGE-001",
) -> ChangeSpecification:

    return ChangeSpecification.model_validate(
        {
            "planId": plan_id,
            "changes": [
                {
                    "itemId": "ITEM-001",
                    "action": "UPDATE",
                    "metadataType": "CustomField",
                    "fullName": (
                        "AI_Test_Session__c."
                        "Status__c"
                    ),
                    "dependencies": [
                        "AI_Test_Session__c"
                    ],
                    "changes": {
                        "addPicklistValues": [
                            "Cancelled"
                        ]
                    },
                }
            ],
            "validationIssues": [],
        }
    )


def test_save_and_get_change_specification():

    store = ChangeSpecStore()

    specification = build_specification()

    store.save(
        specification
    )

    result = store.get(
        "PLAN-CHANGE-001"
    )

    assert result is not None

    assert (
        result.planId
        == "PLAN-CHANGE-001"
    )


def test_get_unknown_change_specification():

    store = ChangeSpecStore()

    result = store.get(
        "PLAN-NOT-FOUND"
    )

    assert result is None


def test_list_change_specifications():

    store = ChangeSpecStore()

    store.save(
        build_specification(
            "PLAN-CHANGE-001"
        )
    )

    store.save(
        build_specification(
            "PLAN-CHANGE-002"
        )
    )

    specifications = store.list()

    assert len(
        specifications
    ) == 2

    plan_ids = {
        specification.planId
        for specification in specifications
    }

    assert plan_ids == {
        "PLAN-CHANGE-001",
        "PLAN-CHANGE-002",
    }


def test_overwrite_existing_change_specification():

    store = ChangeSpecStore()

    first = build_specification(
        "PLAN-CHANGE-001"
    )

    store.save(
        first
    )

    second = (
        ChangeSpecification.model_validate(
            {
                "planId": "PLAN-CHANGE-001",
                "changes": [],
                "validationIssues": [],
            }
        )
    )

    store.save(
        second
    )

    result = store.get(
        "PLAN-CHANGE-001"
    )

    assert result is not None

    assert result.changes == []


def test_delete_change_specification():

    store = ChangeSpecStore()

    store.save(
        build_specification()
    )

    store.delete(
        "PLAN-CHANGE-001"
    )

    result = store.get(
        "PLAN-CHANGE-001"
    )

    assert result is None