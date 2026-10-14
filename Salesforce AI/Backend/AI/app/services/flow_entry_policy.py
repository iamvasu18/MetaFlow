"""Complete omitted entry filters only from an existing equivalent Flow guard."""
from copy import deepcopy
import re


def complete_missing_entry_filters(plan, requirement):
    result=deepcopy(plan)
    if re.search(r'\bevery\s+(?:update|save)\b|\bon\s+all\s+updates\b',requirement,re.I):
        return result
    for item in result.get('items',[]):
        if item.get('metadataType')!='Flow':continue
        config=item.get('config',{})
        if not config.get('doesRequireRecordChangedToMeetCriteria') or config.get('startFilters'):
            continue
        if config.get('triggerType') not in {'RecordBeforeSave','RecordAfterSave'} or config.get('recordTriggerType') not in {'Update','CreateAndUpdate'}:
            continue
        nodes=config.get('elements',[])
        decisions=[n for n in nodes if n.get('kind')=='Decision' and len(n.get('rules',[]))==1 and n.get('rules',[{}])[0].get('conditions') and all(c.get('field','').startswith('$Record.') for c in n['rules'][0]['conditions'])]
        # Multiple outcomes cannot safely be reduced to a single Start predicate.
        if len(decisions)!=1:continue
        decision=decisions[0];rules=decision.get('rules',[])
        if decision.get('defaultNext') is not None or len(rules)!=1 or rules[0].get('conditionLogic')!='and':continue
        conditions=rules[0].get('conditions',[])
        if not conditions or any(not c.get('field','').startswith('$Record.') or c.get('value',{}).get('type')=='Reference' for c in conditions):continue
        # Only reads can precede this guard, otherwise filtering could drop work.
        by_name={n.get('name'):n for n in nodes};name=config.get('startElement');seen=set();safe=True
        while name and name!=decision.get('name'):
            if name in seen or by_name.get(name,{}).get('kind')!='GetRecords':safe=False;break
            seen.add(name);node=by_name[name]
            if node.get('faultNext'):safe=False;break
            name=node.get('next')
        if not safe or name!=decision.get('name'):continue
        config['startFilters']=[dict(deepcopy(c),field=c['field'][len('$Record.'):]) for c in conditions]
        note='Entry filters retain the existing decision conditions. Updates run when the record enters those conditions, preventing repeated side effects; the decision and actions remain unchanged.'
        if note not in result.setdefault('assumptions',[]):result['assumptions'].append(note)
    return result
