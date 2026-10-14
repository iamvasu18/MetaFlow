"""Security-preserving plan normalization for model-generated permission sets."""
from copy import deepcopy
import re

# Conservative: only drop an unrequested grant when requirement has no indication
# of access/authorization work. This never modifies explicitly requested grants.
ACCESS_REQUEST = re.compile(
    r"\b(permission(?:s| set(?:s)?)?|grant|revoke|access|privilege(?:s)?|"
    r"profile(?:s)?|sharing|crud|fls|read.only|edit rights|security role(?:s)?)\b",
    re.I,
)


def sanitize_planned_permission_sets(plan: dict, requirement: str) -> dict:
    """Remove unrelated *new* permission grants, preserving plan dependencies.

    Fail closed on dependencies referencing a would-be removed item rather than
    silently breaking an implementation. For requested permissions, retain them
    and let the strict Pydantic config enforce all grant constraints.
    """
    if ACCESS_REQUEST.search(requirement):
        return plan
    items = plan.get('items', [])
    removed = {item.get('id') for item in items
               if item.get('metadataType') == 'PermissionSet' and item.get('action') == 'CREATE'}
    if not removed:
        return plan
    for item in items:
        if item.get('id') not in removed and removed.intersection(item.get('dependencies') or []):
            raise ValueError('Generated implementation depends on an unrequested Permission Set. '
                             'Planning must resolve this dependency without adding grants.')
    normalized = deepcopy(plan)
    normalized['items'] = [item for item in normalized['items'] if item.get('id') not in removed]
    if not normalized['items']:
        raise ValueError('AI generated only unrequested Permission Sets; no implementation remains.')
    return normalized
