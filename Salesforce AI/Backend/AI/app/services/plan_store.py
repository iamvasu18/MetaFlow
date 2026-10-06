from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


class PlanStore:
    """
    Development-only in-memory store for implementation plans.

    Plans can be created as DRAFT and then moved to APPROVED
    or REJECTED.

    Once a plan is APPROVED or REJECTED, its status cannot
    be changed again.
    """

    ALLOWED_TRANSITIONS = {
        "DRAFT": {
            "APPROVED",
            "REJECTED",
        },
        "APPROVED": set(),
        "REJECTED": set(),
    }

    def __init__(self):
        self._plans: dict[str, ImplementationPlan] = {}

    def save(
        self,
        plan: ImplementationPlan,
    ) -> ImplementationPlan:
        """
        Save an implementation plan.
        """

        self._plans[plan.id] = plan

        return plan

    def get(
        self,
        plan_id: str,
    ) -> ImplementationPlan | None:
        """
        Retrieve a plan by ID.
        """

        return self._plans.get(
            plan_id
        )

    def list(
        self,
    ) -> list[ImplementationPlan]:
        """
        Return all stored plans.
        """

        return list(
            self._plans.values()
        )

    def update_status(
        self,
        plan_id: str,
        status: str,
    ) -> ImplementationPlan:
        """
        Update the status of a stored plan.

        Only valid status transitions are allowed.
        """

        plan = self.get(
            plan_id
        )

        if plan is None:
            raise ValueError(
                f"Plan not found: {plan_id}"
            )

        current_status = plan.status

        allowed_statuses = (
            self.ALLOWED_TRANSITIONS.get(
                current_status,
                set(),
            )
        )

        if status not in allowed_statuses:

            raise ValueError(
                f"Invalid plan status transition: "
                f"{current_status} -> {status}"
            )

        plan.status = status

        return plan