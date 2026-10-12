"""Request-aware Salesforce discovery, including exact object creation checks.

Unknown scope keeps broad checks; omitted inventories are never assumed empty.
"""
import re
from concurrent.futures import ThreadPoolExecutor


def simple_object_request(requirement):
    # Full match deliberately excludes fields, flows, relationships and multiple objects.
    text=requirement.strip().rstrip('.').strip()
    match=re.fullmatch(r'(?:please\s+)?create\s+(?:a\s+|an\s+)?(?:custom\s+)?object\s+(?:(?:named|called)\s+)?["\']?([A-Za-z][A-Za-z0-9_ ]*?)["\']?(?:\s+(?:and\s+)?enable\s+reporting)?',text,re.I)
    if not match:return None
    label=match.group(1).strip()
    explicit_api=label.endswith('__c')
    if re.search(r'\b(with|and|fields?|flows?|lookup|relationship|validation|objects|sharing|permission)\b',label,re.I):return None
    if label.endswith('__c'):
        name=label;label=label[:-3].replace('_',' ')
    else:
        name='_'.join(w[0].upper()+w[1:] for w in label.split())+'__c'
    base=name[:-3]
    if not re.fullmatch(r'[A-Za-z](?:[A-Za-z0-9_]*[A-Za-z0-9])?',base) or '__' in base:return None
    return {'fullName':name,'label':label,'explicitApiName':explicit_api,'enableReports':bool(re.search(r'\benable\s+reporting\b',text,re.I))}


class ComponentConflict(ValueError):
    """A verified org match that needs user intent, not another generation attempt."""
    def __init__(self, kind, name):
        self.question = (
            f"{kind} {name} already exists in the connected org. "
            "Should we reuse it unchanged, or create a separate component with a different name? "
            "If you want to modify the existing component, describe the changes explicitly. "
            "This generation path currently creates new components; it will not overwrite the existing one."
        )
        super().__init__(f"{kind} {name} already exists. No replacement source was generated.")


class MissingObjectDependency(ValueError):
    def __init__(self,name):
        self.question=(f"I couldn't find {name} in the connected org's accessible object metadata. "
            "Should I include a new custom object in this plan, or use a different existing object? "
            "To create it, reply with its label and API name ending in __c, plus any fields the requirement needs. "
            "If it already exists, confirm its API name and the connected user's access. "
            "I'll keep your original requirement and continue after your reply.")
        super().__init__(f'Object dependency is not verified: {name}.')


def check_object_dependencies(requirement,catalog):
    """Ask before generating against explicitly named, unverified parent objects.

    Unrecognized prose remains the planner's responsibility. Catalog absence does
    not prove physical absence: permission and spelling remain possible causes.
    """
    answer=requirement.rsplit('User answer:',1)[1].strip() if 'User answer:' in requirement else ''
    latest_question=requirement.rsplit('Clarification question:',1)[1].split('User answer:',1)[0] if 'Clarification question:' in requirement else ''
    resolved_target=re.search(r"couldn't find ([A-Za-z][A-Za-z0-9_]*)",latest_question)
    replacement=re.search(r'\buse\s+(?:the\s+)?(?:existing\s+)?([A-Za-z][A-Za-z0-9_]*)',answer,re.I)
    replacing=bool(resolved_target and replacement and any(_matches(replacement.group(1),obj.get('name',''),obj.get('label')) for obj in catalog))
    declared=[name for kind,name in requested_components(requirement) if kind=='CustomObject']
    pattern=r'\bcreate\s+(?:(?:a|an|the|new)\s+)?(?:custom\s+)?object\s+(?:(?:named|called)\s+)?[\"\']?([A-Za-z][A-Za-z0-9_]*)'
    for match in re.finditer(pattern,requirement,re.I):
        prefix=requirement[max(0,match.start()-12):match.start()]
        if not re.search(r"(?:do not|don't|dont|not)\s*$",prefix,re.I):declared.append(match.group(1))
    targets=[]
    for pattern in (
        r'\b(?:on|for)\s+(?:the\s+)?(?:object\s+)?[\"\']?([A-Za-z][A-Za-z0-9_]*)[\"\']?\s+object\b',
        r'\b(?:on|for)\s+(?:the\s+)?object\s+[\"\']?([A-Za-z][A-Za-z0-9_]*)',
        r'\b(?:on|for)\s+(?:the\s+)?([A-Za-z][A-Za-z0-9_]*__c)\b',
        r'\blookup\s+to\s+[\"\']?([A-Za-z][A-Za-z0-9_]*)',
        r'\bflow\s+on\s+[\"\']?([A-Za-z][A-Za-z0-9_]*)',
    ):targets.extend(match.group(1) for match in re.finditer(pattern,requirement,re.I))
    for target in dict.fromkeys(targets):
        if replacing and target.casefold()==resolved_target.group(1).casefold():continue
        if any(_matches(target,obj.get('name',''),obj.get('label')) for obj in catalog):continue
        if any(_matches(target,name) or _matches(name,target) for name in declared):continue
        raise MissingObjectDependency(target)



class ObjectNameCollision(ComponentConflict):
    def __init__(self, name, standard):
        category = 'standard' if standard else 'custom'
        ValueError.__init__(self,f"Object already exists: {name} ({category} object). No new object was generated.")
        self.question = (
            f"{name} already exists as a Salesforce {category} object. "
            "Do you want to use the existing object, or create a separate custom object? "
            "For a separate object, provide a distinct name and API name ending in __c. "
            "Renaming a standard object's display label is a separate change; its API name stays unchanged."
        )


def discover_object(pipeline,org,request,api=None):
    name=request['fullName']
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*__c',name):
        raise ValueError('Invalid proposed custom object API name.')
    # Resolve human labels against the connected org, not a built-in alias map.
    if api is not None and not request.get('explicitApiName', False):
        catalog = api.list_objects()
        if not isinstance(catalog, list):
            raise ValueError('Object label discovery did not complete. No source was generated.')
        wanted = request.get('label') or name[:-3].replace('_', ' ')
        found = [obj for obj in catalog if obj.get('name') and any(
            _matches(wanted, obj['name'], obj.get(key))
            for key in ('label', 'labelPlural', 'pluralLabel')
        )]
        if found:
            names = sorted({obj['name'] for obj in found})
            conflict = ComponentConflict('CustomObject', ', '.join(names))
            descriptions = sorted({f"{obj.get('label') or obj['name']} (API name {obj['name']})" for obj in found})
            conflict.question = ('I found existing objects in the connected org: ' + '; '.join(descriptions) +
                '. Which should we use? Reuse an existing object, describe an explicit change, '
                'or provide a distinct label and API name ending in __c for a separate custom object. '
                'No new object has been generated.')
            raise conflict
    # A human label such as Account must not silently become Account__c.
    # Look up the possible standard API name and proposed custom API separately:
    # EntityDefinition rejects OR expressions. Neither check scans the org.
    candidates=[name]
    if not request.get('explicitApiName',False):
        candidates.insert(0,name[:-3].replace('_',''))
    def lookup(candidate):
        query="SELECT QualifiedApiName, Label FROM EntityDefinition WHERE QualifiedApiName = '"+candidate+"'"
        payload={'result':api.query(query,tooling=True)} if api else pipeline.cli(['data','query','--use-tooling-api','--target-org',org,'--query',query])
        result=payload.get('result')
        if not isinstance(result,dict) or not isinstance(result.get('records'),list) or result.get('done') is False:
            raise ValueError('The target object existence check did not complete. Retry after checking the org connection.')
        return result['records']
    if len(candidates)>1:
        with ThreadPoolExecutor(max_workers=2) as pool:
            matches=list(pool.map(lookup,candidates))
    else:
        matches=[lookup(name)]
    for candidate,records in zip(candidates,matches):
        if records:
            existing=str(records[0].get('QualifiedApiName') or candidate)
            raise ObjectNameCollision(existing,not existing.endswith('__c'))
    return {'objects':[],'existingComponents':{},'focusedObjectRequest':request,
        'validationRuleDiscovery':{},'discoveryPolicy':'Exact standard/custom object existence checks completed; unrelated metadata was not requested.'}



INVENTORY_KINDS=('ApexClass','ApexTrigger','LightningComponentBundle','Flow','PermissionSet')


def request_scope(requirement):
    text=requirement.lower()
    kinds=set();known=False;rules=False
    if re.search(r'\bpermission[- ]?sets?\b',text):kinds.add('PermissionSet');known=True
    if re.search(r'\b(lwc|lightning web component|lightning component)\b',text):
        kinds.update(('LightningComponentBundle','ApexClass'));known=True;rules=True
    if re.search(r'\bapex\b',text):
        kinds.add('ApexClass');known=True;rules=True
    if re.search(r'\btrigger\b',text) and not re.search(r'\brecord[- ]triggered\b',text):
        kinds.update(('ApexClass','ApexTrigger'));known=True;rules=True
    if re.search(r'\bflows?\b',text):
        kinds.add('Flow');known=True;rules=True
        if re.search(r'\b(invocable|apex|actions?|subflow)\b',text):kinds.add('ApexClass')
    if re.search(r'\bvalidation rules?\b',text):known=True;rules=True
    if re.search(r'\b(fields?|objects?|picklist|lookup|formula)\b',text):known=True
    # Systems/automation with no declared component family may require any generator.
    ambiguous=not known or bool(re.search(r'\b(system|application|automation|workflow)\b',text) and not kinds)
    if ambiguous:kinds=set(INVENTORY_KINDS);rules=True
    return {'inventoryKinds':tuple(k for k in INVENTORY_KINDS if k in kinds),
        'requiresRules':rules,'mode':'broad-fallback' if ambiguous else 'request-scoped'}


def explicit_objects(requirement,catalog):
    """Prefer complete API names/labels to incidental words such as 'record'."""
    selected=[]
    for obj in catalog:
        name=obj.get('name')
        if not name:continue
        candidates=[name,obj.get('label'),obj.get('labelPlural'),obj.get('pluralLabel')]
        if name.endswith('__c'):candidates.append(name[:-3].replace('_',' '))
        matched=False
        for value in candidates:
            if not value:continue
            value=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',value)
            for phrase in {str(value),name}:
                if re.search(r'(?<![A-Za-z0-9_])'+re.escape(phrase)+r'(?:s)?(?![A-Za-z0-9_])',requirement,re.I):matched=True
        if matched:selected.append(name)
    return list(dict.fromkeys(selected))


def referenced_objects(requirement,context):
    """Expand lookup dependencies explicitly named by the request, not all lookups."""
    result=set()
    for obj in context.get('objects',[]):
        for field in obj.get('fields',[]):
            references=field.get('referenceTo') or []
            if not references:continue
            values=[field.get('name'),field.get('relationshipName')]
            if any(value and re.search(r'(?<![A-Za-z0-9_])'+re.escape(value)+r'(?![A-Za-z0-9_])',requirement,re.I) for value in values):
                result.update(references)
    return result




_FAMILIES = {
    'object': 'CustomObject', 'field': 'CustomField', 'flow': 'Flow',
    'apex class': 'ApexClass', 'apex trigger': 'ApexTrigger',
    'lwc': 'LightningComponentBundle', 'lightning web component': 'LightningComponentBundle',
    'validation rule': 'ValidationRule', 'permission set': 'PermissionSet',
}


def effective_component_requirement(requirement):
    marker='Implement only this follow-up change, using the connected org:'
    if marker in requirement:requirement=requirement.rsplit(marker,1)[1].strip()
    if 'User answer:' in requirement:
        answer=requirement.rsplit('User answer:',1)[1].strip()
        if re.search(r'\bcreate\b',answer,re.I) and not re.search(r"\b(?:do not|don't|dont|not)\s+create\b",answer,re.I):requirement=answer
    return requirement


def requested_components(requirement):
    """Extract explicit creation identities; leave ambiguous wording to the planner."""
    requirement=effective_component_requirement(requirement)
    families='|'.join(re.escape(value) for value in sorted(_FAMILIES,key=len,reverse=True))
    pattern=(r'\bcreate\s+(?:(?:a|an)\s+)?(?:custom\s+)?('+families+
             r')\s+(?:named|called)\s+[\"\']?(.+?)(?=[\"\']?(?:\s+(?:on|with|for|that|and)\b|[.;\n]|$))')
    return [(_FAMILIES[match.group(1).lower()],match.group(2).strip(' \"\''))
            for match in re.finditer(pattern,requirement,re.I)
            if not re.search(r"(?:do not|don't|dont|not)\s*$",requirement[max(0,match.start()-12):match.start()],re.I)]


def _identity(value):
    return re.sub(r'[^a-z0-9]','',str(value).lower())


def _matches(requested, name, label=None):
    # An explicit API name must match exactly. Human names can match a label or
    # normalized API stem, but ambiguity is always resolved through clarification.
    if requested.endswith(('__c','__r')) or '.' in requested:
        return requested.casefold()==name.casefold()
    stem=name[:-3] if name.endswith('__c') else name
    return _identity(requested) in {_identity(name),_identity(stem),_identity(label or '')}


def existing_component_matches(kind, requested, context, parent=None):
    inventory=context.get('existingComponents',{})
    if kind=='CustomObject':
        catalog=context.get('objectCatalog',[])
        entries=[(obj['name'],obj.get('label')) for obj in [*catalog,*context.get('objects',[])] if obj.get('name')]
        entries.extend((obj['name'], obj.get('labelPlural') or obj.get('pluralLabel')) for obj in [*catalog,*context.get('objects',[])] if obj.get('name'))
        entries.extend((name,None) for name in inventory.get(kind,[]))
    elif kind in {'CustomField','ValidationRule'}:
        entries=[]
        for obj in context.get('objects',[]):
            if parent and not _matches(parent,obj['name'],obj.get('label')):continue
            key='fields' if kind=='CustomField' else 'validationRules'
            for value in obj.get(key,[]):
                name=value.get('name') or value.get('fullName','').split('.')[-1]
                if name:entries.append((obj['name']+'.'+name,value.get('label')))
        for name in inventory.get(kind,[]):
            if not parent or _matches(parent,name.split('.')[0]):entries.append((name,None))
        return sorted({full for full,label in entries if _matches(requested,full if '.' in requested else full.split('.')[-1],label)})
    else:
        entries=[(name,None) for name in inventory.get(kind,[])]
    return sorted({name for name,label in entries if _matches(requested,name,label)})


class NoChangesRequired(ValueError):
    code='NO_CHANGE_REQUIRED'


def check_requested_components(requirement, context):
    """Shared pre-model gate for explicitly named components, scoped to their owner."""
    effective=effective_component_requirement(requirement)
    parent_match=re.search(r'\bon\s+(?:the\s+)?[\"\']?([A-Za-z][A-Za-z0-9_ ]*?)(?=[\"\']?(?:\s+object\b|\s+(?:with|and|for)\b|[.;\n]|$))',effective,re.I)
    parent=parent_match.group(1).strip() if parent_match else None
    targets=requested_components(requirement)
    answer=requirement.rsplit('User answer:',1)[1].strip() if 'User answer:' in requirement else ''
    reuse=bool(re.search(r'\b(?:reuse|use)\b',answer,re.I))
    for kind,name in targets:
        matches=existing_component_matches(kind,name,context,parent if kind in {'CustomField','ValidationRule'} else None)
        if matches:
            if reuse and re.search(r'\b(?:add|create|build|change|update|modify|extend|make|implement|generate)\b',answer,re.I):
                continue  # Reuse is a dependency choice, not cancellation of a follow-up.
            if reuse and len(targets)==1:
                raise NoChangesRequired(f'{kind} {matches[0]} will be reused unchanged. No new source or deployment is needed for this request.')
            raise ComponentConflict(kind,', '.join(matches))


def check_planned_components(plan, requirement, context):
    """Apply the same identity checks to model-inferred component names."""
    requested=requested_components(requirement)
    answer=requirement.rsplit('User answer:',1)[1].strip() if 'User answer:' in requirement else ''
    reuse=bool(re.search(r'\b(?:reuse|use)\b',answer,re.I))
    from types import SimpleNamespace
    items=plan.get('items',[]) if isinstance(plan,dict) else plan.items
    has_changes=any((item.get('action') if isinstance(item,dict) else item.action) not in {'NO_CHANGE',None} for item in items)
    for item in items:
        if isinstance(item,dict):
            item=SimpleNamespace(metadataType=item.get('metadataType'),fullName=item.get('fullName'),action=item.get('action'))
        kind,name=item.metadataType,item.fullName
        if not kind or not isinstance(name,str):continue
        if item.action=='NO_CHANGE':
            if reuse and existing_component_matches(kind,name,context):continue
            # Existing dependencies may be reused without pretending they were
            # requested creations. Ask only for explicit matching CREATE requests.
            explicit=[value for family,value in requested if family==kind and _matches(value,name.split('.')[-1])]
            if (explicit or (not has_changes and not requested)) and existing_component_matches(kind,name,context):
                raise ComponentConflict(kind,name)
            continue
        if item.action!='CREATE':continue
        matches=existing_component_matches(kind,name,context)
        if matches:raise ComponentConflict(kind,', '.join(matches))
        if kind=='CustomObject' and name.endswith('__c'):
            # A model-inferred __c suffix is not permission to duplicate a named
            # standard object. Explicit __c names remain intentional requests.
            human=[value for family,value in requested if family==kind and not value.endswith('__c')]
            for value in human:
                matches=existing_component_matches(kind,value,context)
                if matches:raise ComponentConflict(kind,', '.join(matches))
