import pytest

from Backend.AI.app.services.plan_store import (
    PlanStore,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


def create_test_plan():

    return ImplementationPlan.model_validate(
        {
            "id": "PLAN-TEST-001",
            "requirementId": "REQ-TEST-001",
            "summary": "Test plan",
            "assumptions": [],
            "items": [],
            "storyPoints": 1,
            "status": "DRAFT",
        }
    )


def test_save_and_get_plan():

    store = PlanStore()

    plan = create_test_plan()

    store.save(plan)

    result = store.get(
        "PLAN-TEST-001"
    )

    assert result is plan


def test_draft_can_be_approved():

    store = PlanStore()

    plan = create_test_plan()

    store.save(plan)

    result = store.update_status(
        "PLAN-TEST-001",
        "APPROVED",
    )

    assert result.status == "APPROVED"


def test_draft_can_be_rejected():

    store = PlanStore()

    plan = create_test_plan()

    store.save(plan)

    result = store.update_status(
        "PLAN-TEST-001",
        "REJECTED",
    )

    assert result.status == "REJECTED"


def test_approved_plan_cannot_be_rejected():

    store = PlanStore()

    plan = create_test_plan()

    store.save(plan)

    store.update_status(
        "PLAN-TEST-001",
        "APPROVED",
    )

    with pytest.raises(
        ValueError,
        match="Invalid plan status transition",
    ):
        store.update_status(
            "PLAN-TEST-001",
            "REJECTED",
        )


def test_rejected_plan_cannot_be_approved():

    store = PlanStore()

    plan = create_test_plan()

    store.save(plan)

    store.update_status(
        "PLAN-TEST-001",
        "REJECTED",
    )

    with pytest.raises(
        ValueError,
        match="Invalid plan status transition",
    ):
        store.update_status(
            "PLAN-TEST-001",
            "APPROVED",
        )


def test_missing_plan_raises_error():

    store = PlanStore()

    with pytest.raises(
        ValueError,
        match="Plan not found",
    ):
        store.update_status(
            "PLAN-DOES-NOT-EXIST",
            "APPROVED",
        )