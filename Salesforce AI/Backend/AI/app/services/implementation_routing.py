"""Small routing constraints for UI requests; explicit technology always wins."""
import re


def prefers_home_search_lwc(requirement):
    if 'Implementation choice: create a Lightning Web Component (LightningComponentBundle)' in requirement:
        return True
    if re.search(r'\b(?:flow|apex|visualforce|aura)\b', requirement, re.I):
        return False
    return bool(re.search(r'\b(?:create|build|implement|add)\b', requirement, re.I)
                and re.search(r'\b(?:component|lwc|lightning web component)\b', requirement, re.I)
                and re.search(r'\bhome\s*page\b', requirement, re.I)
                and re.search(r'\bsearch(?:able)?\b', requirement, re.I))


def resolve_ui_requirement(requirement):
    if 'Implementation choice: create a Lightning Web Component (LightningComponentBundle)' in requirement:
        return requirement
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
    if not prefers_home_search_lwc(requirement):
        return
    items = data.get('items', [])
    lwcs = [item for item in items if item.get('metadataType') == 'LightningComponentBundle']
    if not lwcs or any(item.get('metadataType') == 'Flow' for item in items):
        raise ImplementationChoiceError('This Home-page search component requires a LightningComponentBundle, not a Screen Flow. Preserve the complete requested behavior.')
    if any('lightning__HomePage' not in (item.get('config') or {}).get('targets', []) for item in lwcs):
        raise ImplementationChoiceError('Expose the requested search component on lightning__HomePage.')
