"""Small routing constraints for UI requests; explicit technology always wins."""
import re


def requested_lwc_target(requirement):
    """Return an explicitly requested LWC page target, if the request is for a UI component."""
    if not re.search(r"\b(?:lwc|lightning web component|component)\b", requirement, re.I):
        return None
    if re.search(r"\b(?:app\s*page|application\s*page)\b", requirement, re.I):
        return "lightning__AppPage"
    if re.search(r"\b(?:record\s*page)\b", requirement, re.I):
        return "lightning__RecordPage"
    if re.search(r"\b(?:home\s*page)\b", requirement, re.I):
        return "lightning__HomePage"
    if re.search(r"\b(?:screen\s*flow|flow\s*screen)\b", requirement, re.I):
        return "lightning__FlowScreen"
    return None


def prefers_home_search_lwc(requirement):
    if 'Implementation choice: create a Lightning Web Component (LightningComponentBundle)' in requirement:
        return True
    if re.search(r'\b(?:flow|apex|visualforce|aura)\b', requirement, re.I):
        return False
    return bool(re.search(r'\b(?:create|build|implement|add)\b', requirement, re.I)
                and re.search(r'\b(?:component|lwc|lightning web component)\b', requirement, re.I)
                and re.search(r'\bhome\s*page\b', requirement, re.I)
                and re.search(r'\bsearch(?:able)?\b', requirement, re.I))


def prefers_explicit_create_lwc(requirement):
    return bool(re.match(r"^\s*(?:please\s+)?(?:create|build|implement|develop|add)\b", requirement, re.I)
                and re.search(r"\b(?:lwc|lightning web component)\b", requirement, re.I))


def resolve_ui_requirement(requirement):
    if 'Implementation choice: create a Lightning Web Component (LightningComponentBundle)' in requirement:
        return requirement
    target = requested_lwc_target(requirement)
    if target and prefers_explicit_create_lwc(requirement):
        return requirement + (f"\nImplementation choice: create a Lightning Web Component (LightningComponentBundle) "
                              f"exposed on {target}. Preserve every explicitly requested feature, including "
                              "search filters, related-record behavior and quick-create actions when requested. "
                              "Prefer LDS/UI API where sufficient, and validated Apex only when necessary. "
                              "Do not replace the requested LWC with a Screen Flow. "
                              "Treat optional UI details as defaults, never invent required org metadata. "
                              "Flag unsupported features without silently dropping them.")
    if not prefers_home_search_lwc(requirement):
        return requirement
    return requirement + ('\nImplementation choice: create a Lightning Web Component (LightningComponentBundle) '
                          'exposed on lightning__HomePage, using LDS/UI API. Preserve all requested search, '
                          'selected-record details and related-record display. Do not replace this UI with a Screen Flow. '
                          'Use accessible records only; document ordinary display-field defaults. '
                          'If any requested behavior is unsupported, report that limitation instead of omitting it.')


class ImplementationChoiceError(ValueError):
    pass


def check_ui_plan(requirement, data):
    target = requested_lwc_target(requirement) if prefers_explicit_create_lwc(requirement) else None
    if not target and not prefers_home_search_lwc(requirement):
        return
    target = target or "lightning__HomePage"
    items = data.get('items', [])
    lwcs = [item for item in items if item.get('metadataType') == 'LightningComponentBundle']
    if not lwcs or any(item.get('metadataType') == 'Flow' for item in items):
        raise ImplementationChoiceError('This requested Lightning component requires a LightningComponentBundle, not a Screen Flow. Preserve the complete requested behavior.')
    if any(target not in (item.get('config') or {}).get('targets', []) for item in lwcs):
        raise ImplementationChoiceError(f'Expose the requested component on {target}.')
