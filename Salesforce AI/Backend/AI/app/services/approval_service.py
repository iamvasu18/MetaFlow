from Backend.AI.app.services.plan_store import PlanStore
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


class PlanApprovalService:
    """
    Handles explicit approval and rejection of
    Salesforce implementation plans.

    Approval is separate from deployment.
    An approved plan becomes eligible for the
    deployment workflow.
    """

    def __init__(
        self,
        plan_store: PlanStore,
    ):
        self.plan_store = plan_store

    def approve(
        self,
        plan_id: str,
    ) -> ImplementationPlan:
        """
        Approve a DRAFT implementation plan.
        """

        return self.plan_store.update_status(
            plan_id=plan_id,
            status="APPROVED",
        )

    def reject(
        self,
        plan_id: str,
    ) -> ImplementationPlan:
        """
        Reject a DRAFT implementation plan.
        """

        return self.plan_store.update_status(
            plan_id=plan_id,
            status="REJECTED",
        )

    def get_plan(
        self,
        plan_id: str,
    ) -> ImplementationPlan:
        """
        Retrieve a stored implementation plan.
        """

        plan = self.plan_store.get(
            plan_id
        )

        if plan is None:
            raise ValueError(
                f"Plan not found: {plan_id}"
            )

        return plan