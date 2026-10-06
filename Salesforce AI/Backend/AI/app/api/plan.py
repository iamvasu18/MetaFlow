from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from Backend.AI.app.providers.mock_provider import (
    MockProvider,
)
from Backend.AI.app.services.planning_service import (
    PlanningService,
)
from Backend.AI.app.services.plan_store import (
    PlanStore,
)
from Backend.AI.app.services.approval_service import (
    PlanApprovalService,
)
from Backend.AI.app.salesforce.metadata_service import (
    SalesforceMetadataService,
)


router = APIRouter(
    prefix="/plan",
    tags=["Planning"],
)


class PlanRequest(BaseModel):
    requirement: str


class PlanResponse(BaseModel):
    plan: dict


class PlanStoreResponse(BaseModel):
    plan: dict


# ---------------------------------------------------------
# Shared development store
# ---------------------------------------------------------

plan_store = PlanStore()

approval_service = PlanApprovalService(
    plan_store=plan_store
)


# ---------------------------------------------------------
# Generate plan
# ---------------------------------------------------------

@router.post(
    "",
    response_model=PlanResponse,
)
def generate_plan(
    request: PlanRequest,
):
    """
    Generate a Salesforce implementation plan
    from a natural-language requirement.

    Newly generated plans are stored as DRAFT.
    """

    # ---------------------------------------------
    # 1. Salesforce metadata service
    # ---------------------------------------------

    metadata_service = SalesforceMetadataService(
        target_org="AIOrg"
    )

    # ---------------------------------------------
    # 2. AI provider
    # ---------------------------------------------

    provider = MockProvider()

    # ---------------------------------------------
    # 3. Planning service
    # ---------------------------------------------

    planning_service = PlanningService(
        provider=provider,
        metadata_service=metadata_service,
    )

    # ---------------------------------------------
    # 4. Generate implementation plan
    # ---------------------------------------------

    try:

        plan = planning_service.generate_plan(
            requirement=request.requirement,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    # ---------------------------------------------
    # 5. Store plan
    # ---------------------------------------------

    plan_store.save(plan)

    # ---------------------------------------------
    # 6. Return plan
    # ---------------------------------------------

    return PlanResponse(
        plan=plan.model_dump(
            by_alias=True
        )
    )


# ---------------------------------------------------------
# Get stored plan
# ---------------------------------------------------------

@router.get(
    "/{plan_id}",
    response_model=PlanStoreResponse,
)
def get_plan(
    plan_id: str,
):
    """
    Retrieve a previously generated plan.
    """

    try:

        plan = approval_service.get_plan(
            plan_id
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return PlanStoreResponse(
        plan=plan.model_dump(
            by_alias=True
        )
    )


# ---------------------------------------------------------
# Approve plan
# ---------------------------------------------------------

@router.post(
    "/{plan_id}/approve",
    response_model=PlanStoreResponse,
)
def approve_plan(
    plan_id: str,
):
    """
    Explicitly approve a DRAFT implementation plan.

    Approval does not deploy anything.
    """

    try:

        plan = approval_service.approve(
            plan_id
        )

    except ValueError as exc:

        message = str(exc)

        if message.startswith(
            "Plan not found:"
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc

    return PlanStoreResponse(
        plan=plan.model_dump(
            by_alias=True
        )
    )


# ---------------------------------------------------------
# Reject plan
# ---------------------------------------------------------

@router.post(
    "/{plan_id}/reject",
    response_model=PlanStoreResponse,
)
def reject_plan(
    plan_id: str,
):
    """
    Explicitly reject a DRAFT implementation plan.

    Rejection does not deploy anything.
    """

    try:

        plan = approval_service.reject(
            plan_id
        )

    except ValueError as exc:

        message = str(exc)

        if message.startswith(
            "Plan not found:"
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc

    return PlanStoreResponse(
        plan=plan.model_dump(
            by_alias=True
        )
    )