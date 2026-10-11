"""Application CREATE-object policy, applied only before plan approval."""
from copy import deepcopy
import re

CUSTOM_OBJECT_DEFAULTS = {'nameFieldType': 'Text', 'deploymentStatus': 'Deployed', 'sharingModel': 'Read'}
CUSTOM_OBJECT_KEYS = {'pluralLabel', 'nameFieldLabel', 'enableReports', *CUSTOM_OBJECT_DEFAULTS}
CUSTOM_OBJECT_POLICY_PROMPT = """
APPLICATION CUSTOM OBJECT CREATE POLICY (authoritative executable constraints)
For CREATE CustomObject, when the user does not request object sharing settings,
use config.sharingModel = "Read". Never invent ReadWrite or Private.
Use nameFieldType = "Text" and deploymentStatus = "Deployed" when unspecified.
The only supported config keys are enableReports (boolean), pluralLabel, nameFieldLabel, nameFieldType,
deploymentStatus, sharingModel. Surface unsupported explicit configuration as a
validation error; do not silently replace a user's request with the default.
Do not change approved plans or apply these CREATE defaults to UPDATE items.
""".strip()

# Deliberately narrow: only an unambiguous, standalone object-creation request
# permits replacing an AI-invented sharing value. Complex requirements fail
# validation instead of relying on a guessed natural-language interpretation.
_BASIC_CREATE = re.compile(r'\s*(?:please\s+)?create\s+(?:a\s+|an\s+)?(?:[A-Za-z][A-Za-z0-9_]*\s+){1,6}(?:custom\s+)?object\s*[.!]?\s*', re.I)
_ACCESS_WORDS = re.compile(r'\b(?:sharing\s*model|sharingModel|sharing|access|visibility|permissions?|owners?|readwrite|read\s*[-/]\s*write|private|public|confidential)\b|\b(?:only|everyone|anyone)\b.{0,35}\b(?:see|view|access|edit)\b|\b(?:grant|restrict|deny|allow)\b.{0,35}\b(?:access|visibility)\b', re.I)
_SUPPORTED_CLAUSE = re.compile(r'\b(?:set\s+)?sharingModel\s*(?:to|=|:)\s*["\']?Read["\']?\b', re.I)


def custom_object_config_errors(config):
    if config is None:
        return []  # Omitted values are filled before approval by the service.
    if not isinstance(config, dict):
        return ['CREATE CustomObject config must be an object.']
    errors = []
    if 'enableReports' in config and not isinstance(config['enableReports'], bool):
        errors.append('CustomObject enableReports must be boolean.')
    for key in sorted(set(config) - CUSTOM_OBJECT_KEYS):
        errors.append(f'Unsupported CustomObject config: {key}.')
    for key, expected in CUSTOM_OBJECT_DEFAULTS.items():
        if key in config and config[key] != expected:
            errors.append(f'CustomObject {key} must be {expected}.')
    for key in ('pluralLabel', 'nameFieldLabel'):
        if key in config and (not isinstance(config[key], str) or not config[key].strip()):
            errors.append(f'CustomObject {key} must be a non-empty string.')
    return errors


def apply_custom_object_defaults(plan_data, requirement):
    """Copy a draft response; never mutate a stored/approved plan.

    This is a conservative policy guard, not a general natural-language parser.
    Unresolved access language requires review, even if AI emitted Read.
    """
    result = deepcopy(plan_data)
    items = result.get('items')
    if not isinstance(items, list):
        return result  # Structural validator owns malformed response errors.
    objects = [i for i in items if isinstance(i, dict) and i.get('action') == 'CREATE' and i.get('metadataType') == 'CustomObject']
    if not objects:
        return result
    if result.get('status', 'DRAFT') != 'DRAFT' or any(i.get('approval', 'PENDING') != 'PENDING' for i in objects):
        raise ValueError('CustomObject defaults can only be applied to a draft, pending plan.')
    remaining = _SUPPORTED_CLAUSE.sub('', requirement)
    if _ACCESS_WORDS.search(remaining):
        raise ValueError('The requirement includes access or sharing instructions that need review. This version supports only its default object sharing configuration (Read); no requested access settings were changed.')
    simple_request = bool(_BASIC_CREATE.fullmatch(requirement))
    for item in objects:
        config = item.get('config')
        if config is None:
            config = {}
            item['config'] = config
        if not isinstance(config, dict):
            continue
        if re.search(r'\benable\s+report(?:ing|s)\b', requirement, re.I):
            config['enableReports'] = True
        if simple_request:
            config['sharingModel'] = 'Read'
        for key, value in CUSTOM_OBJECT_DEFAULTS.items():
            config.setdefault(key, value)
    return result
