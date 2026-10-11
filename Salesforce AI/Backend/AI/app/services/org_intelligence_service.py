"""Read-only Salesforce metrics. Credentials never enter returned snapshots."""
import re
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException


class Unavailable(Exception):
    pass



def normalize_limits(raw):
    result = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            continue
        maximum, remaining = value.get('Max'), value.get('Remaining')
        if not isinstance(maximum, (int, float)) or not isinstance(remaining, (int, float)):
            continue
        used = max(0, maximum - remaining)
        result[name] = {'used': used, 'limit': maximum, 'remaining': remaining,
                        'percentage': round(used / maximum * 100, 1) if maximum > 0 else None}
    return result


def collect_intelligence(org, expected_id=None):
    from Backend.AI.app.services.salesforce_api_client import SalesforceApiClient
    from Backend.AI.app.services.flow_generator import api_version
    from Backend.AI.app.account_api import PROJECT_ROOT
    api=SalesforceApiClient(org['user_id'],org['id'],api_version(PROJECT_ROOT))
    records=api.query('SELECT Id, Name, OrganizationType, IsSandbox FROM Organization LIMIT 1')['records']
    if len(records)!=1 or not isinstance(records[0],dict) or not re.fullmatch(r'00D[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',str(records[0].get('Id',''))):
        raise HTTPException(502,'Salesforce organization identity could not be verified.')
    identity=records[0]
    if expected_id and identity['Id'][:15]!=expected_id[:15]:
        raise HTTPException(409,'This saved connection points to a different Salesforce org. Reconnect it in Settings.')
    version=api.version
    warnings = {}
    # Reuse the bounded HTTP pool; credentials are attached per request, never
    # shared as client default headers across users or orgs.
    def get(path,params=None):
        try:return api.get(path,params)
        except HTTPException as error:
            if error.status_code==409:raise
            raise Unavailable(str(error.detail)) from None
    base=api.base
    def query(soql,tooling=False):
        try:return api.query(soql,tooling)['records']
        except HTTPException as error:
            if error.status_code==409:raise
            raise Unavailable(str(error.detail)) from None

    def count(soql, tooling=False):
        rows = query(soql, tooling)
        return rows[0].get('expr0', 0) if rows else 0

    tasks = {
        'limits': lambda: normalize_limits(get(base + '/limits')),
        'licenses': lambda: [{k: r.get(k) for k in ('Name', 'TotalLicenses', 'UsedLicenses')} for r in query('SELECT Name, TotalLicenses, UsedLicenses FROM UserLicense ORDER BY Name')],
        'totalUsers': lambda: count('SELECT COUNT(Id) FROM User'),
        'enabledUsers': lambda: count('SELECT COUNT(Id) FROM User WHERE IsActive = true'),
        'recentUsers': lambda: count('SELECT COUNT(Id) FROM User WHERE IsActive = true AND LastLoginDate = LAST_N_DAYS:30'),
        'neverLoggedIn': lambda: count('SELECT COUNT(Id) FROM User WHERE IsActive = true AND LastLoginDate = null'),
        'frozenUsers': lambda: count('SELECT COUNT(Id) FROM UserLogin WHERE IsFrozen = true'),
        'profiles': lambda: count('SELECT COUNT(Id) FROM Profile'),
        'permissionSets': lambda: count('SELECT COUNT(Id) FROM PermissionSet WHERE IsOwnedByProfile = false'),
        'recentLogins': lambda: count('SELECT COUNT(Id) FROM LoginHistory WHERE LoginTime = LAST_N_DAYS:30'),
        'failedLogins': lambda: count("SELECT COUNT(Id) FROM LoginHistory WHERE LoginTime = LAST_N_DAYS:30 AND Status != 'Success'"),
        'customObjects': lambda: [{'name': r['name'], 'label': r['label']} for r in get(base + '/sobjects').get('sobjects', []) if r.get('custom') and r['name'].endswith('__c')],
        'customFields': lambda: count('SELECT COUNT(Id) FROM CustomField', True),
        'activeFlows': lambda: count('SELECT COUNT(Id) FROM FlowDefinition WHERE ActiveVersionId != null', True),
        'inactiveFlows': lambda: count('SELECT COUNT(Id) FROM FlowDefinition WHERE ActiveVersionId = null', True),
        'apexClasses': lambda: count('SELECT COUNT(Id) FROM ApexClass', True),
        'validationRules': lambda: count('SELECT COUNT(Id) FROM ValidationRule', True),
        'scheduledJobs': lambda: count("SELECT COUNT(Id) FROM CronTrigger WHERE State NOT IN ('DELETED', 'COMPLETE', 'ERROR')"),
    }
    values = {}
    def fetch(item):
        key, task = item
        try:
            return key, task(), None
        except Unavailable as error:
            return key, None, str(error)
    # Bound API concurrency while keeping a missing permission from blocking all metrics.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for key, value, warning in pool.map(fetch, tasks.items()):
            values[key] = value
            if warning:
                warnings[key] = warning

    return {'organization': {'id': identity['Id'], 'name': identity['Name'],
                'environment': 'Sandbox' if identity.get('IsSandbox') else identity.get('OrganizationType', org['type']),
                'apiVersion': 'v' + version}, 'syncedAt': time.time(),
            'metrics': values, 'warnings': warnings}
