"""Small task-specific standards shared by planning, generation and repair.

These are generation guidance. Actual approval/deployment gates remain backend
validators and the target org's check-only validation, never model claims.
"""
import re

COMMON = '''REQUIREMENT COMPLETENESS
Inventory every requested trigger, condition, branch, read/write, UI action and outcome before generating. Map each to a concrete artifact and test. Preserve explicit technology, names, timing and access. Do not replace an unsupported operation with a simpler one or omit it. Report a specific unsupported capability or one genuine blocker. Default optional design settings and document assumptions. Unknown org facts are not absent facts. Never claim compilation, coverage or runtime tests passed from source inspection. All writes require the application's exact-source approval/deployment process.'''

FLOW = '''FLOW DESIGN
Choose before-save for same-record field changes and after-save for related writes/actions; after-save is still in the save transaction, not after commit. Preserve explicitly requested create/update timing, entry conditions and every branch. doesRequireRecordChangedToMeetCriteria=true requires nonempty valid Start filters. Preserve the existing decision guard; never set this flag with empty startFilters or remove the guard to fix a schema error. Avoid repeated side effects through deliberate idempotency, not by silently narrowing the trigger. Resolve all objects, field types, valid picklists, queues, action signatures and subflow interfaces from verified facts. A queue has members, not a single intrinsic user owner: choose a verified task assignee or ask one necessary question. Declare record resources, their object types and collections before references. Connect only exact declared node names. Query before loops, accumulate changes, then bulk-write after loops. Guard empty query results. Use supported fault paths with meaningful failure handling; never swallow failures or invent an error object. Keep schedule time zone and future start verified. Preserve Flow versions/status and require an explicit activation operation. Do not generate unsupported Orchestration, Data Cloud triggers or element kinds merely because Salesforce supports them.'''

APEX = '''APEX DESIGN AND TESTS
Use handler/service separation when triggers need it, but do not add unnecessary layers. Process every trigger record; compare old/new states and use idempotency appropriate to repeated updates. Use Sets/Maps and bulk queries/DML, bound input and result sizes; nested loops need bounded fanout rather than a blanket prohibition. Choose Queueable for suitable async work, Batch for large populations, Schedulable as a launcher; retain explicit future requests within their restrictions. Preserve required transactional/partial-success semantics and inspect every SaveResult. Apply verified record sharing and explicit user-mode queries/DML under the supported contract. Bind query values; no hardcoded IDs, credentials or permission bypasses. Tests create valid org-specific data and assert persisted outcomes for success, empty, invalid, failure and bulk cases. Trigger tests exercise 200 records and unchanged updates; async tests submit real entry points within startTest/stopTest. Do not fake negative tests, swallow assertions or inflate coverage with test-only production branches. Coverage and governor behavior need Salesforce execution; mocks verify expected dependency behavior rather than replacing all business logic.'''

LWC = '''LWC DESIGN AND BEHAVIOR
Use LDS/UI API where the actual requirement fits; use verified same-package Apex for custom transactional/query behavior. Keep controller, companion tests, imports and parameter names coordinated. Cacheable methods are read-only; mutations are imperative. Refresh the entire wired Apex result after mutations, and notify LDS when appropriate; show refresh failures. Render loading, empty, success and permission/error states and prevent duplicate mutations. Ignore late responses for stale record selections. Use accessible Lightning base components, labels, keyboard operability and stable list keys. Do not mutate public properties or wire data. Clean up permitted timers/listeners/subscriptions; use only modules supported by the checker. Keep results bounded or paginate. Use behavioral tests for loading, empty/error responses, mutation success/failure, stale requests, refresh and cleanup. Compilation/lint alone does not establish those behaviors. Use Promise.then/catch under this service's current syntax contract; do not generate unsupported integrations or external imports.'''

INTEGRATION = '''CROSS-COMPONENT CONTRACT
Declare dependencies explicitly and generate them in dependency order. Flow-invocable methods need a verified bulk-compatible input/output contract. LWC calls require public/global static AuraEnabled methods, cacheable only for reads, exact named parameters and supported serialized types; Apex inner classes are not a supported LWC parameter/return contract. Changing a controller signature requires coordinated caller and test updates. Repair only affected artifacts and their verified dependents; preserve unrelated components and every requested behavior. Recheck saved source and invalidate previous approval/validation whenever it changes.'''


def select_rules(requirement, *, components=(), phase='planning'):
    """Select by component identity when available, otherwise explicit signals.

    Planning includes Flow design for untyped record automation; explicit Apex
    or LWC requests don't inherit an unrelated full Flow schema/rule pack.
    """
    types={str(c.get('metadataType', '')) for c in components if isinstance(c,dict)}
    text=requirement.lower()
    packs=[]
    apex=bool(types & {'ApexClass','ApexTrigger'}) or bool(re.search(r'\b(apex|queueable|batch|schedulable|future|trigger|controller|invocable)\b',text))
    lwc='LightningComponentBundle' in types or bool(re.search(r'\b(lwc|lightning|component|dashboard|screen ui)\b',text))
    flow='Flow' in types or bool(re.search(r'\bflow\b',text)) or bool(re.search(r'\b(automation|automatically|when|whenever)\b',text)) and not types and not apex and not lwc
    if flow:packs.append(('Flow',FLOW))
    if apex:packs.append(('Apex',APEX))
    if lwc:packs.append(('LWC',LWC))
    if len(packs)>1 or lwc and apex:packs.append(('Integration',INTEGRATION))
    return COMMON+'\n\n'+'\n\n'.join(name+' RULES\n'+rules for name,rules in packs)
