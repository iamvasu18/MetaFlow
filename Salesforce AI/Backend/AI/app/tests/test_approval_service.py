import pytest

from Backend.AI.app.services.approval_service import (
    PlanApprovalService,
)
from Backend.AI.app.services.plan_store import (
    PlanStore,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


def create_plan(status="DRAFT"):

    return ImplementationPlan.model_validate(
        {
            "id": "PLAN-APPROVAL-001",
            "requirementId": "REQ-APPROVAL-001",
            "summary": "Test approval plan.",
            "assumptions": [],
            "items": [],
            "storyPoints": 1,
            "status": status,
        }
    )


def create_service():

    store = PlanStore()

    service = PlanApprovalService(
        plan_store=store
    )

    return store, service


def test_draft_plan_can_be_approved():

    store, service = create_service()

    plan = create_plan()

    store.save(plan)

    result = service.approve(
        "PLAN-APPROVAL-001"
    )

    assert result.status == "APPROVED"

    assert (
        store.get(
            "PLAN-APPROVAL-001"
        ).status
        == "APPROVED"
    )


def test_draft_plan_can_be_rejected():

    store, service = create_service()

    plan = create_plan()

    store.save(plan)

    result = service.reject(
        "PLAN-APPROVAL-001"
    )

    assert result.status == "REJECTED"

    assert (
        store.get(
            "PLAN-APPROVAL-001"
        ).status
        == "REJECTED"
    )


def test_approved_plan_cannot_be_approved_again():

    store, service = create_service()

    plan = create_plan(
        status="APPROVED"
    )

    store.save(plan)

    with pytest.raises(
        ValueError,
        match="Invalid plan status transition",
    ):

        service.approve(
            "PLAN-APPROVAL-001"
        )


def test_rejected_plan_cannot_be_approved():

    store, service = create_service()

    plan = create_plan(
        status="REJECTED"
    )

    store.save(plan)

    with pytest.raises(
        ValueError,
        match="Invalid plan status transition",
    ):

        service.approve(
            "PLAN-APPROVAL-001"
        )


def test_unknown_plan_cannot_be_approved():

    _, service = create_service()

    with pytest.raises(
        ValueError,
        match="Plan not found",
    ):

        service.approve(
            "PLAN-DOES-NOT-EXIST"
        )


def test_unknown_plan_cannot_be_rejected():

    _, service = create_service()

    with pytest.raises(
        ValueError,
        match="Plan not found",
    ):

        service.reject(
            "PLAN-DOES-NOT-EXIST"
        )


def test_get_plan_returns_stored_plan():

    store, service = create_service()

    plan = create_plan()

    store.save(plan)

    result = service.get_plan(
        "PLAN-APPROVAL-001"
    )

    assert result.id == (
        "PLAN-APPROVAL-001"
    )

    assert result.status == "DRAFT"