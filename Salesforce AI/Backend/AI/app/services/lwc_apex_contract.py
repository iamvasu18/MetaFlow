"""Derive LWC-callable methods only from the package's generated controller source."""
import re
from Backend.AI.app.services.apex_validator import lexical_source


def controller_contract(files, names):
    methods = {}
    for name in names:
        source = files.get(f'force-app/main/default/classes/{name}.cls', '')
        code, errors = lexical_source(source)
        if errors:
            raise ValueError(f'{name}: invalid controller source delimiters.')
        inner_classes = {m.group(1).casefold() for m in re.finditer(r'\bclass\s+(\w+)', code, re.I) if code[:m.start()].count('{') - code[:m.start()].count('}') >= 1}
        pattern = r'@AuraEnabled(?:\s*\((?P<options>[^)]*)\))?\s+(?:public|global)\s+static\s+(?P<returns>[\w.<>,\s]+?)\s+(?P<method>\w+)\s*\((?P<params>[^)]*)\)\s*\{'
        for match in re.finditer(pattern,code,re.I):
            if code[:match.start()].count('{') - code[:match.start()].count('}') != 1:
                continue
            signature_types = match['returns'] + ' ' + re.sub(r'\b\w+\s*(?=,|$)', '', match['params'])
            if inner_classes & {token.casefold() for token in re.findall(r'\b\w+\b', signature_types)}:
                raise ValueError('LWC Apex method cannot expose an inner class parameter or return type: ' + name + '.' + match['method'])
            key = name + '.' + match['method']
            if key in methods:
                raise ValueError('Overloaded AuraEnabled methods are not supported: ' + key)
            end, depth = match.end(), 1
            while end < len(code) and depth:
                depth += (code[end] == '{') - (code[end] == '}')
                end += 1
            readonly = bool(re.search(r'cacheable\s*=\s*true', match['options'] or '', re.I))
            if readonly and re.search(r'\b(?:insert|update|upsert|delete|undelete|merge)\b|\bDatabase\s*\.\s*(?:insert|update|upsert|delete|undelete|merge)\s*\(', code[match.end():end], re.I):
                raise ValueError('Cacheable Apex method must be read-only: ' + key)
            methods[key] = {'cacheable':bool(re.search(r'cacheable\s*=\s*true',match['options'] or '',re.I)),
                            'parameters':match['params'].strip(), 'parameterNames':re.findall(r'\b(\w+)\s*(?=,|$)', re.sub(r'<[^>]*>', '',match['params'])), 'returnType':match['returns'].strip()}
    if names and not methods:
        raise ValueError('LWC dependencies have no public/global static AuraEnabled methods.')
    return methods


def check_package_lwc(files, plan, context, version, checker):
    """Recheck imports against the actual saved controllers after a source repair."""
    from Backend.AI.app.services.lwc_service import LWCSource
    items = plan.get('items', [])
    for item in items:
        if item.get('metadataType') != 'LightningComponentBundle' or item.get('action') == 'NO_CHANGE':
            continue
        name = item['fullName']
        dependencies = set(item.get('dependencies', []))
        names = [row['fullName'] for row in items if row.get('metadataType') == 'ApexClass' and row.get('id') in dependencies]
        methods = controller_contract(files, names) if names else {}
        stem = 'force-app/main/default/lwc/' + name + '/' + name
        checker.check_source(name, LWCSource(html=files[stem+'.html'], javascript=files[stem+'.js'], css=files.get(stem+'.css','')), context, version, methods)
