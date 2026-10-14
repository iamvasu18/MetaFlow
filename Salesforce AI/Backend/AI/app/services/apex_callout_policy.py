"""Narrow outbound HTTP contract: existing Named Credentials, never raw URLs."""
import re
from Backend.AI.app.services.apex_validator import lexical_source, loop_bodies


def discover_callout_context(context, org, version, requirement):
    if not re.search(r'\b(callouts?|named credential|httprequest|external api)\b',requirement,re.I):
        return context
    from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
    transport=owned_metadata_api(org,version)
    if transport is None:
        raise ValueError('Connect Salesforce to verify an existing Named Credential before generating an HTTP callout.')
    names=[row['fullName'] for row in transport.list_metadata('NamedCredential')]
    requested = re.search(r'\bnamed credential\s+(?:named\s+|called\s+)?[\"\']?([A-Za-z][A-Za-z0-9_]*)', requirement, re.I)
    if not requested:
        requested = re.search(r'\b([A-Za-z][A-Za-z0-9_]*)\s+named credential\b',requirement,re.I)
    if not requested:
        raise ValueError('Specify which existing Named Credential this integration should use; the destination cannot be safely guessed.')
    selected = [name for name in names if name.casefold() == requested.group(1).casefold()]
    if not selected:
        raise ValueError('The requested Named Credential was not found in the accessible inventory. Check its API name and metadata access.')
    return dict(context, namedCredentials=selected)


def check_callout_source(source, context, kind):
    code, _=lexical_source(source)
    if not re.search(r'\b(?:HttpRequest|Http)\b',code,re.I):return False
    allowed={name.casefold() for name in context.get('namedCredentials',[])}
    endpoints=list(re.finditer(r'\.\s*setEndpoint\s*\(',code,re.I))
    if not endpoints or not allowed:
        raise ValueError('HTTP callouts require a verified existing Named Credential and explicit endpoint.')
    for match in endpoints:
        argument=source[match.end():]
        endpoint=re.match(r"\s*'callout:([A-Za-z][A-Za-z0-9_]*)[^'\r\n]*'\s*\)",argument,re.I)
        if not endpoint or endpoint.group(1).casefold() not in allowed:
            raise ValueError('HTTP endpoints must be literal callout:VerifiedNamedCredential/path references; raw or dynamic URLs are unsupported.')
    timeouts=re.findall(r'\.\s*setTimeout\s*\(\s*(\d+)\s*\)',code,re.I)
    if not timeouts or any(not 1<=int(value)<=120000 for value in timeouts):
        raise ValueError('HTTP callouts require an explicit bounded timeout of 1..120000 milliseconds.')
    if kind in {'Batchable','Queueable'} and not re.search(r'\bDatabase\s*\.\s*AllowsCallouts\b',code,re.I):
        raise ValueError('Async HTTP jobs require Database.AllowsCallouts.')
    for body in loop_bodies(code):
        if re.search(r'\.\s*send\s*\(',body,re.I):
            raise ValueError('Per-record HTTP send calls inside loops are outside this bulk-safe callout contract.')
    return True
