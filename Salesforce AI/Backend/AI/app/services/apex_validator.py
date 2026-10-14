"""Focused lexical checks. Salesforce compilation is still mandatory.

These checks are not a complete Apex parser, security analyzer or proof of
bulk safety. Comments/literals are masked before structural checks.
"""
from __future__ import annotations
import re
from typing import Any
from Backend.AI.app.services.salesforce_capability_registry import SalesforceCapabilityRegistry

APEX_TRIGGER_EVENTS = {'before insert','before update','before delete','after insert','after update','after delete','after undelete'}
APEX_IDENTIFIER = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,254}$')
CLASS_DECLARATION = re.compile(r'\bclass\s+(?P<name>[A-Za-z][A-Za-z0-9_]*)\b', re.I)
TRIGGER_DECLARATION = re.compile(r'\btrigger\s+(?P<name>\w+)\s+on\s+(?P<sobject>\w+)\s*\((?P<events>[^)]*)\)',re.I)


def lexical_source(source):
    """Return code with strings/comments masked and delimiter errors."""
    masked = list(source)
    errors, stack = [], []
    pairs = {')':'(', ']':'[', '}':'{'}
    index = 0
    while index < len(source):
        start = index
        if source.startswith('//', index):
            end = source.find('\n', index)
            index = len(source) if end < 0 else end
        elif source.startswith('/*', index):
            end = source.find('*/', index + 2)
            if end < 0:
                errors.append('Unterminated Apex block comment.')
                index = len(source)
            else:
                index = end + 2
        elif source[index] == "'":
            index += 1
            closed = False
            while index < len(source):
                if source[index] == '\\':
                    index += 2
                elif source[index] == "'":
                    index += 1
                    closed = True
                    break
                else:
                    index += 1
            if not closed:
                errors.append('Unterminated Apex string literal.')
            index = min(index, len(source))
        else:
            char = source[index]
            if char in '([{':
                stack.append(char)
            elif char in ')]}':
                if not stack or stack.pop() != pairs[char]:
                    errors.append('Mismatched Apex delimiters.')
            index += 1
            continue
        for position in range(start, index):
            if source[position] not in '\r\n':
                masked[position] = ' '
    if stack:
        errors.append('Unbalanced Apex delimiters.')
    return ''.join(masked), list(dict.fromkeys(errors))


def loop_bodies(code):
    # Includes nested and unbraced bodies; excludes a SOQL-for-loop header.
    for match in re.finditer(r'\b(?:for|while)\s*\(',code,re.I):
        position, depth = match.end(), 1
        while position < len(code) and depth:
            depth += (code[position] == '(') - (code[position] == ')')
            position += 1
        while position < len(code) and code[position].isspace():
            position += 1
        end = position
        if position < len(code) and code[position] == '{':
            end, depth = position + 1, 1
            while end < len(code) and depth:
                depth += (code[end] == '{') - (code[end] == '}')
                end += 1
        else:
            end = code.find(';',position)
            if end < 0:
                end = len(code)
        yield code[position:end]
    # A do-while body is also a loop; conservatively inspect its block.
    for match in re.finditer(r'\bdo\s*\{',code,re.I):
        end, depth = match.end(), 1
        while end < len(code) and depth:
            depth += (code[end] == '{') - (code[end] == '}')
            end += 1
        yield code[match.end():end]


def _warnings(code, source):
    warnings = []
    for body in loop_bodies(code):
        if re.search(r'\bSELECT\b|\bDatabase\s*\.\s*(?:query|countQuery)(?:WithBinds)?\s*\(',body,re.I):
            warnings.append('Query execution appears inside a loop; bulkification review is required.')
        if re.search(r'\b(?:insert|update|upsert|delete|undelete|merge)\b',body,re.I):
            warnings.append('DML appears inside a loop; bulkification review is required.')
    if re.search(r'\bDatabase\s*\.\s*(?:query|countQuery)(?:WithBinds)?\s*\(',code,re.I):
        warnings.append('Dynamic SOQL requires bind-variable and injection review.')
    if re.search(r"'[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?'",source):
        warnings.append('Possible hard-coded Salesforce Id; review configuration and test data.')
    return list(dict.fromkeys(warnings))


def _soql_clause_errors(code):
    """Catch clause-order failures without treating strings/comments as queries.

    This is intentionally a small, conservative check, not an Apex/SOQL parser.
    Salesforce check-only compilation remains authoritative.
    """
    errors = []
    for query in re.findall(r'\[\s*SELECT\b.*?\]', code, re.I | re.S):
        user_mode = re.search(r'\bWITH\s+(?:USER_MODE|SYSTEM_MODE)\b', query, re.I)
        if not user_mode:
            continue
        later = query[user_mode.end():]
        if re.search(r'\b(?:WHERE|GROUP\s+BY|HAVING)\b', later, re.I):
            errors.append('SOQL WITH USER_MODE/SYSTEM_MODE must follow WHERE, GROUP BY and HAVING clauses; it cannot precede WHERE.')
    return list(dict.fromkeys(errors))


def _blocking_bulk_findings(code):
    errors = []
    for body in loop_bodies(code):
        if re.search(r'\bSELECT\b|\bDatabase\s*\.\s*(?:query|countQuery)(?:WithBinds)?\s*\(', body, re.I):
            errors.append('Query execution inside a loop is prohibited; collect keys and query once outside the loop.')
        if re.search(r'(?<![\w.])(?:insert|update|upsert|delete|undelete|merge)\s+(?=[A-Za-z_(])|\bDatabase\s*\.\s*(?:insert|update|upsert|delete|undelete|merge)\s*\(', body, re.I):
            errors.append('DML execution inside a loop is prohibited; collect records and write once outside the loop.')
    return list(dict.fromkeys(errors))


def validate_apex_class_config(full_name: str, config: dict[str, Any]) -> list[str]:
    errors = []
    if not isinstance(full_name,str) or not APEX_IDENTIFIER.fullmatch(full_name):
        errors.append('ApexClass fullName must be a valid Apex identifier.')
    if not isinstance(config,dict):
        return errors + ['ApexClass requires a config object.']
    kind, body = config.get('apexKind'), config.get('body')
    if not SalesforceCapabilityRegistry.is_valid_apex_kind(kind):
        errors.append(f'Unsupported apexKind: {kind!r}.')
    if not isinstance(body,str) or not body.strip():
        return errors + ['ApexClass config.body is required.']
    code, structural = lexical_source(body)
    errors.extend(structural)
    errors.extend(_blocking_bulk_findings(code))
    errors.extend(_soql_clause_errors(code))
    if re.search(r'\b(?:System\s*\.\s*)?Assert\s*\.\s*(?:assertEquals|assertNotEquals|assertNotNull|assertNull|assertTrue|assertFalse)\s*\(',code,re.I):
        errors.append('Invalid Assert class method. Use System.Assert.areEqual/areNotEqual/isNotNull/isNull/isTrue/isFalse, or legacy System.assertEquals directly.')
    if re.search(r'\bnew\s+(?:System\s*\.\s*)?Exception\s*\(',code,re.I):
        errors.append('Exception cannot be constructed directly. Define a concrete custom class extending Exception.')
    for query in re.findall(r'\[\s*SELECT\b.*?\]',code,re.I|re.S):
        if re.search(r'(?<![.\w])NOW\s*\(',query,re.I):
            errors.append('NOW() is not a SOQL function. Set a Datetime cutoff in Apex and bind :cutoff in the query.')
    if kind == 'Test' and re.search(r'\b(?:enqueueJob|executeBatch|schedule)\s*\(',code,re.I):
        if not (re.search(r'\bTest\s*\.\s*startTest\s*\(',code,re.I) and re.search(r'\bTest\s*\.\s*stopTest\s*\(',code,re.I)):
            errors.append('Async tests must invoke the job between Test.startTest() and Test.stopTest().')
    for method in re.finditer(r'@future(?:\s*\([^)]*\))?\s+([^{};]+)\{', code,re.I):
        if not re.search(r'\bstatic\s+void\b',method.group(1),re.I):
            errors.append('@future methods must be static and return void.')
        params = re.search(r'\(([^)]*)\)', method.group(1))
        if params:
            types = re.sub(r'\b[A-Za-z][A-Za-z0-9_]*\s*(?=,|$)', '', params.group(1))
            allowed = {'list','set','map','id','boolean','integer','long','decimal','double','string','date','datetime','time','blob'}
            if any(word.lower() not in allowed for word in re.findall(r'[A-Za-z][A-Za-z0-9_]*',types)):
                errors.append('@future parameters must be primitive types or collections of primitive types.')
    match = CLASS_DECLARATION.search(code)
    if not match:
        errors.append('ApexClass body must contain a class declaration.')
    elif match.group('name') != full_name:
        errors.append(f"ApexClass declaration name '{match.group('name')}' does not match fullName '{full_name}'.")
    if match and kind != 'Test' and not re.search(r'\b(?:public|global)\b',code[:match.start()],re.I):
        errors.append('Non-test top-level Apex classes require public or global visibility.')
    warnings = _warnings(code,body)
    if kind != 'Test':
        if re.search(r'\bwithout\s+sharing\b',code,re.I):
            warnings.append('without sharing requires an explicit business and security review.')
        elif not re.search(r'\b(?:with|inherited)\s+sharing\b',code,re.I):
            warnings.append('Declare an explicit sharing mode for maintenance across API versions.')
    interfaces = {'Batchable':r'Database\s*\.\s*Batchable','Queueable':'Queueable','Schedulable':'Schedulable'}
    if kind in interfaces and not re.search(r'\bimplements\b[^{}]*\b'+interfaces[kind]+r'\b',code,re.I):
        errors.append(f'{kind} Apex must implement its required interface.')
    for required_kind, pattern in [('Invocable',r'@InvocableMethod\b'),('RestResource',r'@RestResource\b'),('SoapWebService',r'\bwebservice\b')]:
        if kind == required_kind and not re.search(pattern,code,re.I):
            errors.append(f'{kind} Apex lacks its required annotation/declaration.')
    if kind == 'Test':
        if not re.search(r'@IsTest\b',code,re.I):
            errors.append('Test Apex must contain @IsTest.')
        if not re.search(r'\b(?:System\s*\.\s*assert\w*|Assert\s*\.\s*\w+)\s*\(',code,re.I):
            warnings.append('Test Apex contains no obvious assertion; meaningful tests are required.')
    return errors + ['WARNING: '+warning for warning in warnings]


def validate_apex_trigger_config(full_name: str, config: dict[str, Any]) -> list[str]:
    errors = []
    if not isinstance(full_name,str) or not APEX_IDENTIFIER.fullmatch(full_name):
        errors.append('ApexTrigger fullName must be a valid Apex identifier.')
    if not isinstance(config,dict):
        return errors + ['ApexTrigger requires a config object.']
    sobject = config.get('sobject')
    if not isinstance(sobject,str) or not APEX_IDENTIFIER.fullmatch(sobject):
        errors.append('ApexTrigger config.sobject must be a valid Apex identifier.')
    events = config.get('events')
    normalized = []
    if not isinstance(events,list) or not events:
        errors.append('ApexTrigger config.events must be a non-empty list.')
    else:
        for event in events:
            if not isinstance(event,str) or event.strip().lower() not in APEX_TRIGGER_EVENTS:
                errors.append(f'Unsupported Apex trigger event: {event!r}.')
            else:
                normalized.append(event.strip().lower())
        if len(normalized) != len(set(normalized)):
            errors.append('Apex trigger events must be unique.')
    body = config.get('body')
    if not isinstance(body,str) or not body.strip():
        return errors + ['ApexTrigger config.body is required.']
    code, structural = lexical_source(body)
    errors.extend(structural)
    errors.extend(_blocking_bulk_findings(code))
    errors.extend(_soql_clause_errors(code))
    match = TRIGGER_DECLARATION.search(code)
    if not match:
        errors.append('ApexTrigger body must contain a trigger declaration.')
    else:
        if match.group('name') != full_name:
            errors.append('ApexTrigger declaration name does not match fullName.')
        if match.group('sobject') != sobject:
            errors.append('ApexTrigger declaration object does not match config.sobject.')
        if set(e.strip().lower() for e in match.group('events').split(',')) != set(normalized):
            errors.append('ApexTrigger declaration events do not match config.events.')
    return errors + ['WARNING: '+warning for warning in _warnings(code,body)]


def validate_apex_source(metadata_type, full_name, config):
    validator = {'ApexClass':validate_apex_class_config,'ApexTrigger':validate_apex_trigger_config}.get(metadata_type)
    if validator is None:
        return [f'Unsupported Apex metadata type: {metadata_type}'], []
    raw = validator(full_name,config)
    return ([item for item in raw if not item.startswith('WARNING: ')],
            [item.removeprefix('WARNING: ') for item in raw if item.startswith('WARNING: ')])
