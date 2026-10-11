"""Build a dependency-complete subset of a saved package, without AI calls."""
from copy import deepcopy
import json
import re
from .component_source_service import component_files


def select_components(package, selected, expected_hash, fingerprint):
    if expected_hash != package['sourceHash']:
        raise ValueError('Source changed. Reload before selecting components.')
    fingerprint_before = fingerprint(package)
    if fingerprint_before != expected_hash:
        raise ValueError('Saved source fingerprint changed.')
    keys = {c['metadataType'] + ':' + c['fullName']: c for c in package['components']}
    if not selected or not set(selected) <= keys.keys():
        raise ValueError('Select at least one existing component.')
    items = package['plan']['items']
    by_id = {i['id']: i for i in items}
    chosen = {i['id'] for i in items if i['metadataType'] + ':' + i['fullName'] in selected}
    pending = list(chosen)
    while pending:
        item = by_id[pending.pop()]
        dependencies = set(item.get('dependencies', []))
        if item['metadataType'] in {'ApexClass', 'ApexTrigger'}:
            dependencies.update(i['id'] for i in items if i['metadataType'] == 'ApexClass' and i['fullName'] in package['testClasses'])
        # Generated source references can expose dependencies omitted by the model.
        source = json.dumps(item.get('config') or {})
        if item['action'] != 'NO_CHANGE':
            source += '\n' + '\n'.join(component_files(package, item['fullName']).values())
        for candidate in items:
            if candidate['id'] == item['id']:
                continue
            name = candidate['fullName']
            reference = name.split('.')[-1] if candidate['metadataType'] == 'CustomField' else name
            if re.search(r'(?<![A-Za-z0-9_])' + re.escape(reference) + r'(?![A-Za-z0-9_])', source):
                dependencies.add(candidate['id'])
            if item['metadataType'] in {'CustomField', 'ValidationRule'} and candidate['metadataType'] == 'CustomObject' and item['fullName'].split('.')[0] == name:
                dependencies.add(candidate['id'])
        for dependency in dependencies:
            if dependency not in by_id:
                raise ValueError('A selected component has an unresolved dependency: ' + dependency)
            if dependency not in chosen:
                chosen.add(dependency)
                pending.append(dependency)
    updated = deepcopy(package)
    updated['plan']['items'] = [deepcopy(i) for i in items if i['id'] in chosen]
    selected_keys = {i['metadataType'] + ':' + i['fullName'] for i in updated['plan']['items'] if i['action'] == 'CREATE'}
    updated['components'] = [deepcopy(c) for k, c in keys.items() if k in selected_keys]
    paths = set()
    for component in updated['components']:
        paths.update(component_files(package, component['fullName']))
    updated['baseFiles'] = {p: v for p, v in package['baseFiles'].items() if p in paths}
    updated['files'] = deepcopy(updated['baseFiles'])
    if updated.get('metadataSpecification'):
        updated['metadataSpecification']['metadata'] = [i for i in updated['metadataSpecification']['metadata'] if i['itemId'] in chosen]
        if not updated['metadataSpecification']['metadata']:
            updated['metadataSpecification'] = None
    updated['testClasses'] = [name for name in package['testClasses'] if 'ApexClass:' + name in selected_keys]
    updated.update(state='generated', approvedHash=None, validatedHash=None, layoutReady=False)
    for key in ('jobId', 'operation', 'lastResult', 'error', 'errorDetails', 'operationStartedAt', 'operationSeconds'):
        updated.pop(key, None)
    updated['selectionAddedDependencies'] = [i['fullName'] for i in updated['plan']['items'] if i['metadataType'] + ':' + i['fullName'] not in selected and i['action'] == 'CREATE']
    updated['sourceHash'] = fingerprint(updated)
    return updated
