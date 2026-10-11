"""Project draft/approved CREATE dependencies for checks; never invent org facts."""
from copy import deepcopy


def context_with_planned_components(plan, context):
    result = deepcopy(context)
    objects = {o['name']: o for o in result.get('objects', []) if o.get('name')}
    items = plan.get('items', [])
    for item in items:
        if item.get('metadataType') == 'CustomObject' and item.get('action') == 'CREATE':
            name = item.get('fullName')
            if name not in objects:
                objects[name] = {'name': name, 'label': item.get('label') or name,
                    'planned': True, 'createable': True, 'updateable': True,
                    'queryable': True, 'fields': [
                        {'name': 'Id', 'type': 'id', 'createable': False, 'updateable': False},
                        {'name': 'Name', 'type': 'string', 'createable': True, 'updateable': True}]}
    families = {'Text':'string', 'LongTextArea':'textarea', 'Number':'double',
        'Currency':'currency', 'Percent':'percent', 'Date':'date', 'DateTime':'datetime',
        'Checkbox':'boolean', 'Picklist':'picklist', 'MultiselectPicklist':'multipicklist',
        'Lookup':'reference', 'MasterDetail':'reference', 'Email':'email', 'Phone':'phone',
        'Url':'url'}
    for item in items:
        if item.get('metadataType') != 'CustomField' or item.get('action') != 'CREATE':
            continue
        full = item.get('fullName', '')
        if '.' not in full:
            continue  # Structural validation owns malformed identities.
        obj, name = full.split('.', 1)
        if obj not in objects:
            raise ValueError(f'Field parent {obj} is neither verified in the org nor created in this plan.')
        fields = objects[obj].setdefault('fields', [])
        if any(f.get('name') == name for f in fields):
            continue  # Live field facts take priority; CREATE collision gate remains authoritative.
        config = item.get('config') or {}
        kind = config.get('fieldType') or config.get('type')
        field = {'name': name, 'label': item.get('label') or name,
            'type': families.get(kind, str(kind).lower()), 'planned': True,
            'calculated': bool(config.get('formula')), 'createable': not bool(config.get('formula')),
            'updateable': not bool(config.get('formula')), 'nillable': not config.get('required', False),
            'required': config.get('required', False)}
        for key in ('scale', 'precision', 'length'):
            if key in config:
                field[key] = config[key]
        if config.get('referenceTo'):
            field['referenceTo'] = [config['referenceTo']]
        if config.get('formula'):
            field['calculatedFormula'] = config['formula']
        field['values'] = config.get('values', [])
        fields.append(field)
    result['objects'] = list(objects.values())
    return result
