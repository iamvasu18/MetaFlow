"""Conservative, deterministic staged planning for explicit multi-item requirements.

This module never authorizes changes or attempts to synthesize Salesforce metadata.
It only identifies self-contained, enumerated user tasks; uncertain requests are
left to the ordinary planner instead of being silently split.
"""
from __future__ import annotations

import re
from uuid import uuid4

from Backend.AI.app.validators.plan_validator import ImplementationPlan


class StagedPlanningUnavailable(ValueError):
    """A requirement cannot be safely decomposed with the available evidence."""


_ITEM = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s+)(\S.*)$")
_CROSS_REFERENCE = re.compile(
    r"\b(?:above|below|previous|following|same|these|those|it|them|its|their|"
    r"dependent|depends|after that|then|respectively|as described)\b", re.I
)


def independent_requirements(requirement: str, *, max_parts: int = 12) -> list[str]:
    """Accept only explicit, separately enumerated tasks, without implicit references.

    A conservative refusal is intentional: arbitrary paragraph or sentence slicing
    is unsafe for Salesforce relationships and ordered automation.
    """
    lines = requirement.splitlines()
    items: list[str] = []
    outside: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        match = _ITEM.fullmatch(line)
        if match:
            items.append(match.group(1).strip())
        else:
            outside.append(line.strip())
    if outside or len(items) < 2 or len(items) > max_parts:
        raise StagedPlanningUnavailable(
            "Staged planning requires 2–12 independent, enumerated requirements "
            "with no unassigned introductory or continuation text."
        )
    if any(_CROSS_REFERENCE.search(item) for item in items):
        raise StagedPlanningUnavailable(
            "The requirements contain cross-item references and must be planned together."
        )
    if len(set(items)) != len(items):
        raise StagedPlanningUnavailable("Repeated requirement items cannot be safely merged.")
    return items


def merge_independent_plans(plans: list[ImplementationPlan]) -> dict:
    """Merge validated draft plans, refusing ambiguous names or dependencies.

    IDs are remapped; all original item configuration is preserved unchanged.
    Backend validation must still run over the merged plan.
    """
    if len(plans) < 2:
        raise StagedPlanningUnavailable("At least two stage plans are required.")
    items = []
    summaries = []
    assumptions = []
    names = set()
    for index, plan in enumerate(plans, start=1):
        if plan.status != "DRAFT" or not plan.items:
            raise StagedPlanningUnavailable("Every stage must produce a nonempty DRAFT plan.")
        old_ids = [item.id for item in plan.items]
        if len(set(old_ids)) != len(old_ids):
            raise StagedPlanningUnavailable("Stage contains duplicate item IDs.")
        id_map = {old_id: f"STAGE{index}_{old_id}" for old_id in old_ids}
        for item in plan.items:
            if item.approval != "PENDING" or item.deployment is not None:
                raise StagedPlanningUnavailable("A stage attempted to approve or deploy changes.")
            key = (item.metadataType, item.fullName)
            if key in names:
                raise StagedPlanningUnavailable(
                    "Several stages refer to the same Salesforce component; coordinated planning is required."
                )
            names.add(key)
            if any(dep not in id_map for dep in item.dependencies):
                raise StagedPlanningUnavailable(
                    "Stage references another stage or an unknown dependency."
                )
            payload = item.model_dump()
            payload["id"] = id_map[item.id]
            payload["dependencies"] = [id_map[dep] for dep in item.dependencies]
            items.append(payload)
        summaries.append(plan.summary)
        assumptions.extend(plan.assumptions)
    if any(not summary.strip() for summary in summaries):
        raise StagedPlanningUnavailable("A stage is missing its summary.")
    return {
        "id": f"PLAN-{uuid4().hex}",
        "requirementId": f"REQ-{uuid4().hex}",
        "summary": " | ".join(summaries),
        "assumptions": list(dict.fromkeys(assumptions)),
        "items": items,
        "status": "DRAFT",
    }
