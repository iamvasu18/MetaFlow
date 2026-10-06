def test_approve_plan_endpoint():

    from Backend.AI.app.main import plan_store
    from Backend.AI.app.validators.plan_validator import (
        ImplementationPlan,
    )

    plan_store._plans.clear()

    plan = ImplementationPlan.model_validate(
        {
            "id": "PLAN-API-APPROVE-001",
            "requirementId": "REQ-API-001",
            "summary": "Test approval",
            "assumptions": [],
            "items": [],
            "storyPoints": 1,
            "status": "DRAFT",
        }
    )

    plan_store.save(plan)

    from fastapi.testclient import TestClient
    from Backend.AI.app.main import app

    client = TestClient(app)

    response = client.post(
        "/api/plans/PLAN-API-APPROVE-001/approve"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == "PLAN-API-APPROVE-001"
    assert data["status"] == "APPROVED"


def test_reject_plan_endpoint():

    from Backend.AI.app.main import plan_store
    from Backend.AI.app.validators.plan_validator import (
        ImplementationPlan,
    )

    plan_store._plans.clear()

    plan = ImplementationPlan.model_validate(
        {
            "id": "PLAN-API-REJECT-001",
            "requirementId": "REQ-API-002",
            "summary": "Test rejection",
            "assumptions": [],
            "items": [],
            "storyPoints": 1,
            "status": "DRAFT",
        }
    )

    plan_store.save(plan)

    from fastapi.testclient import TestClient
    from Backend.AI.app.main import app

    client = TestClient(app)

    response = client.post(
        "/api/plans/PLAN-API-REJECT-001/reject"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == "PLAN-API-REJECT-001"
    assert data["status"] == "REJECTED"


def test_approved_plan_cannot_be_rejected_through_api():

    from Backend.AI.app.main import plan_store
    from Backend.AI.app.validators.plan_validator import (
        ImplementationPlan,
    )

    plan_store._plans.clear()

    plan = ImplementationPlan.model_validate(
        {
            "id": "PLAN-API-LOCK-001",
            "requirementId": "REQ-API-003",
            "summary": "Test locked approval",
            "assumptions": [],
            "items": [],
            "storyPoints": 1,
            "status": "DRAFT",
        }
    )

    plan_store.save(plan)

    from fastapi.testclient import TestClient
    from Backend.AI.app.main import app

    client = TestClient(app)

    approve_response = client.post(
        "/api/plans/PLAN-API-LOCK-001/approve"
    )

    assert approve_response.status_code == 200

    reject_response = client.post(
        "/api/plans/PLAN-API-LOCK-001/reject"
    )

    assert reject_response.status_code == 422

    assert (
        "Only DRAFT plans can be rejected."
        in reject_response.json()["detail"]
    )


def test_rejected_plan_cannot_be_approved_through_api():

    from Backend.AI.app.main import plan_store
    from Backend.AI.app.validators.plan_validator import (
        ImplementationPlan,
    )

    plan_store._plans.clear()

    plan = ImplementationPlan.model_validate(
        {
            "id": "PLAN-API-LOCK-002",
            "requirementId": "REQ-API-004",
            "summary": "Test locked rejection",
            "assumptions": [],
            "items": [],
            "storyPoints": 1,
            "status": "DRAFT",
        }
    )

    plan_store.save(plan)

    from fastapi.testclient import TestClient
    from Backend.AI.app.main import app

    client = TestClient(app)

    reject_response = client.post(
        "/api/plans/PLAN-API-LOCK-002/reject"
    )

    assert reject_response.status_code == 200

    approve_response = client.post(
        "/api/plans/PLAN-API-LOCK-002/approve"
    )

    assert approve_response.status_code == 422

    assert (
        "Only DRAFT plans can be approved."
        in approve_response.json()["detail"]
    )


def test_approve_nonexistent_plan():

    from fastapi.testclient import TestClient
    from Backend.AI.app.main import app

    client = TestClient(app)

    response = client.post(
        "/api/plans/PLAN-DOES-NOT-EXIST/approve"
    )

    assert response.status_code == 404

    assert (
        "Plan not found"
        in response.json()["detail"]
    )