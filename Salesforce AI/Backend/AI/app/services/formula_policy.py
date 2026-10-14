"""Catch known picklist misuse; Salesforce remains the complete formula validator."""
import re
import xml.etree.ElementTree as ET


def validate_picklist_formulas(plan, context, files=None):
    items=plan.get('items',[]) if isinstance(plan,dict) else [item.model_dump() for item in plan.items]
    kinds={(obj['name'],field['name']):str(field.get('type','')).lower() for obj in context.get('objects',[]) for field in obj.get('fields',[]) if field.get('name')}
    for item in items:
        if item.get('metadataType')=='CustomField' and '.' in item.get('fullName',''):
            obj,field=item['fullName'].split('.',1)
            config=item.get('config') or {}
            kinds[obj,field]=str(config.get('fieldType') or config.get('type') or '').lower()
    for item in items:
        if item.get('metadataType')!='ValidationRule' or item.get('action')=='NO_CHANGE':
            continue
        obj,rule=item['fullName'].split('.',1)
        formula=(item.get('config') or {}).get('errorConditionFormula','')
        path=f'force-app/main/default/objects/{obj}/validationRules/{rule}.validationRule-meta.xml'
        if files is not None and path in files:
            root=ET.fromstring(files[path])
            formula=root.findtext('{http://soap.sforce.com/2006/04/metadata}errorConditionFormula') or ''
        # Mask quoted literals, retaining their positions and all operator syntax.
        code=re.sub(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''', lambda m:' '*len(m.group()),formula,flags=re.X)
        for (parent,field),kind in kinds.items():
            if parent!=obj or kind not in {'picklist','multipicklist','multiselectpicklist'}:
                continue
            identifier=r'(?<![\w.])'+re.escape(field)+r'\b'
            if re.search(identifier+r'\s*(?:<>|!=|>=|<=|=|>|<)',code,re.I) or re.search(r'(?:<>|!=|>=|<=|=|>|<)\s*'+identifier,code,re.I):
                raise ValueError(f'{item["fullName"]}: {field} is a picklist. Use ISPICKVAL/CASE/TEXT for single picklists or INCLUDES for multi-select values, rather than a direct comparison.')
            if kind=='picklist' and re.search(r'\bISBLANK\s*\(\s*'+identifier+r'\s*\)',code,re.I):
                raise ValueError(f'{item["fullName"]}: use ISBLANK(TEXT({field})) for a single picklist.')
