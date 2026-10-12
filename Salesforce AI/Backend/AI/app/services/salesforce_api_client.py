"""Owned read-only Salesforce API transport. No CLI fallback or metadata writes."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import logging
import re
from threading import Lock
from time import perf_counter
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException

_POOL = None
_POOL_LOCK = Lock()
_REFRESH_LOCKS = {}
_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]*\Z')
_ID = re.compile(r'[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?\Z')


def instance_url(value):
    try:
        parsed=urlparse(value if isinstance(value,str) else '')
        port=parsed.port
    except ValueError:
        raise HTTPException(502,'Invalid saved Salesforce instance URL.') from None
    if (parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.salesforce.com')
            or port or parsed.username or parsed.password or parsed.path not in {'','/'} or parsed.query or parsed.fragment):
        raise HTTPException(502,'Invalid saved Salesforce instance URL.')
    return value.rstrip('/')


def http_pool():
    global _POOL
    with _POOL_LOCK:
        if _POOL is None or _POOL.is_closed:
            _POOL=httpx.Client(timeout=httpx.Timeout(20,connect=10),follow_redirects=False,
                limits=httpx.Limits(max_connections=16,max_keepalive_connections=8))
        return _POOL


def encrypt_org_tokens(tokens,auth_host):
    from Backend.AI.app.services.integration_service import cipher
    import json
    from .oauth_connection import auth_host as validate_auth_host
    auth_host=validate_auth_host(auth_host)
    if not isinstance(tokens,dict) or not all(isinstance(tokens.get(k),str) and tokens[k] for k in ('access_token','refresh_token','instance_url')):
        raise HTTPException(502,'Salesforce did not supply complete OAuth credentials.')
    value={key:tokens[key] for key in ('access_token','refresh_token','instance_url')}
    if tokens.get('oauth_client'):value['oauth_client']=deepcopy(tokens['oauth_client'])
    value['instance_url']=instance_url(value['instance_url']);value['auth_host']=auth_host
    return cipher().encrypt(json.dumps(value).encode()).decode()


def save_org_tokens(owner,org,tokens,auth_host):
    from Backend.AI.app.account_api import db
    encrypted=encrypt_org_tokens(tokens,auth_host)
    with db() as c:
        if not c.execute('SELECT id FROM orgs WHERE id=? AND user_id=?',(org,owner)).fetchone():
            raise HTTPException(404,'Salesforce connection not found.')
        c.execute('INSERT OR REPLACE INTO org_tokens VALUES(?,?,?)',(owner,org,encrypted))


def load_org_tokens(owner,org):
    from Backend.AI.app.account_api import db
    from Backend.AI.app.services.integration_service import cipher
    import json
    with db() as c:
        owned=c.execute('SELECT instance FROM orgs WHERE id=? AND user_id=?',(org,owner)).fetchone()
        row=c.execute('SELECT payload FROM org_tokens WHERE user_id=? AND org_id=?',(owner,org)).fetchone()
    if not owned:raise HTTPException(404,'Salesforce connection not found.')
    if not row:raise HTTPException(409,'Reconnect this Salesforce org once in Settings to enable API discovery.')
    try:
        value=json.loads(cipher().decrypt(row['payload'].encode()))
    except Exception:
        raise HTTPException(503,'Saved Salesforce credentials cannot be decrypted. Restore the server encryption key or reconnect this org.') from None
    if not isinstance(value,dict):
        raise HTTPException(503,'Saved Salesforce credentials are invalid. Reconnect this org.')
    value['instance_url']=instance_url(value.get('instance_url'))
    from .oauth_connection import auth_host as validate_auth_host
    value['auth_host']=validate_auth_host(value.get('auth_host'))
    if not all(isinstance(value.get(k),str) and value[k] for k in ('access_token','refresh_token')):
        raise HTTPException(503,'Saved Salesforce credentials are invalid. Reconnect this org.')
    if value['instance_url'].lower()!=instance_url(owned['instance']).lower():
        raise HTTPException(409,'Saved Salesforce instance changed. Reconnect this org.')
    return value


class SalesforceApiClient:
    def __init__(self,owner,org,version='67.0',http=None):
        if not owner or not org:raise HTTPException(401,'An owned Salesforce connection is required.')
        if not re.fullmatch(r'\d{2,3}\.0',str(version)):raise ValueError('Invalid Salesforce API version.')
        self.owner,self.org,self.version,self.http=owner,org,str(version),http
        self.base='/services/data/v'+self.version
        # ContextVars do not propagate to discovery threads. Capture owner here,
        # then verify ownership on every credential read and refresh write.

    def _refresh(self,failed_token):
        from Backend.AI.app.account_api import client as oauth_client
        import os
        with _POOL_LOCK:lock=_REFRESH_LOCKS.setdefault((self.owner,self.org),Lock())
        from Backend.AI.app.services.shared_plan_lock import shared_plan_lock
        with lock, shared_plan_lock('oauth-refresh:' + self.owner + ':' + self.org):
            saved=load_org_tokens(self.owner,self.org)
            if saved['access_token']!=failed_token:return saved
            from .oauth_connection import refresh_credentials
            data={'grant_type':'refresh_token','refresh_token':saved['refresh_token'],**refresh_credentials(saved)}
            try:response=(self.http or http_pool()).post(saved['auth_host']+'/services/oauth2/token',data=data)
            except httpx.HTTPError:raise HTTPException(503,'Salesforce token refresh could not be completed. Retry when connectivity is restored.') from None
            if response.status_code in {400,401,403}:raise HTTPException(409,'Salesforce authorization expired or was revoked. Reconnect this org in Settings.')
            if response.status_code!=200:raise HTTPException(502,'Salesforce token refresh returned an unexpected response.')
            try:updated=response.json()
            except ValueError:raise HTTPException(502,'Salesforce token refresh returned unreadable data.') from None
            if not isinstance(updated,dict) or not updated.get('access_token'):raise HTTPException(502,'Salesforce token refresh returned no access token.')
            tokens={**saved,**{k:updated[k] for k in ('access_token','refresh_token','instance_url') if updated.get(k)}}
            # Rotation replaces the encrypted refresh token atomically. A changed
            # instance requires reconnect rather than silently switching targets.
            if instance_url(tokens['instance_url']).lower()!=saved['instance_url'].lower():
                raise HTTPException(409,'Salesforce returned a changed instance URL. Reconnect this saved org.')
            save_org_tokens(self.owner,self.org,tokens,saved['auth_host'])
            return tokens

    def get(self,path,params=None):
        # Read-only allowlist also guards pagination supplied by Salesforce.
        allowed=re.fullmatch(re.escape(self.base)+r'/(?:query(?:/[A-Za-z0-9_-]+)?|tooling/query(?:/[A-Za-z0-9_-]+)?|sobjects(?:/[A-Za-z][A-Za-z0-9_]*/describe)?|limits|actions/(?:custom/(?:apex|emailAlert|flow)|standard/emailSimple))/?',path)
        if not allowed:raise ValueError('Invalid Salesforce API read path.')
        saved=load_org_tokens(self.owner,self.org);started=perf_counter()
        try:
            for attempt in range(2):
                try:response=(self.http or http_pool()).get(saved['instance_url']+path,params=params,
                    headers={'Authorization':'Bearer '+saved['access_token'],'Accept':'application/json'})
                except httpx.HTTPError:raise HTTPException(503,'Salesforce API read timed out or could not be completed.') from None
                if response.status_code==401 and attempt==0:
                    saved=self._refresh(saved['access_token']);continue
                if response.status_code==401:raise HTTPException(409,'Salesforce authorization is unavailable. Reconnect this org.')
                if response.status_code==403:raise HTTPException(403,'Salesforce API access was denied. Check API and metadata permissions for the connected user.')
                if response.status_code==429:raise HTTPException(503,'Salesforce API rate limit reached. Retry later.')
                if response.status_code!=200:
                    code='REQUEST_FAILED'
                    try:
                        errors=response.json()
                        candidate=errors[0].get('errorCode') if isinstance(errors,list) and errors and isinstance(errors[0],dict) else None
                        if isinstance(candidate,str) and re.fullmatch(r'[A-Z_]{1,80}',candidate):code=candidate
                    except (ValueError,TypeError):pass
                    raise HTTPException(502,'Salesforce API read failed ('+code+'). Check metadata permissions and API version.')
                try:return response.json()
                except ValueError:raise HTTPException(502,'Salesforce API returned unreadable JSON.') from None
        finally:
            logging.getLogger(__name__).info('Salesforce discovery transport=api org=%s resource=%s seconds=%.3f',self.org,path.split('/')[-1],perf_counter()-started)

    def query(self,soql,tooling=False):
        route=self.base+('/tooling/query' if tooling else '/query')
        payload=self.get(route,{'q':soql});records=[];seen=set()
        for _ in range(50):
            if not isinstance(payload,dict) or not isinstance(payload.get('records'),list) or not isinstance(payload.get('done'),bool):
                raise HTTPException(502,'Salesforce query did not return a complete inventory response.')
            records.extend(payload['records'])
            if len(records)>50000:raise HTTPException(422,'Salesforce inventory exceeds the supported scope. Narrow the requirement.')
            if payload['done']:return {'records':records,'done':True,'totalSize':len(records)}
            next_path=payload.get('nextRecordsUrl')
            if not isinstance(next_path,str) or next_path in seen or not next_path.startswith(route+'/'):
                raise HTTPException(502,'Salesforce returned an unsafe or repeated query cursor.')
            seen.add(next_path);payload=self.get(next_path)
        raise HTTPException(422,'Salesforce inventory pagination limit reached. Narrow the requirement.')

    def list_objects(self):
        payload=self.get(self.base+'/sobjects')
        if not isinstance(payload,dict) or not isinstance(payload.get('sobjects'),list):raise HTTPException(502,'Salesforce object catalog is incomplete.')
        return payload['sobjects']

    def describe_object(self,name):
        if not isinstance(name,str) or not _NAME.fullmatch(name):raise ValueError('Invalid Salesforce object API name.')
        payload=self.get(self.base+'/sobjects/'+name+'/describe')
        if not isinstance(payload,dict) or payload.get('name')!=name or not isinstance(payload.get('fields'),list):
            raise HTTPException(502,'Salesforce object describe is incomplete or belongs to another object.')
        return payload

    def list_components(self,kind):
        if kind == 'PermissionSet':
            rows = self.query('SELECT Name, Label, NamespacePrefix FROM PermissionSet WHERE IsOwnedByProfile = false')['records']
            result = []
            for row in rows:
                name, namespace = row.get('Name'), row.get('NamespacePrefix')
                if not isinstance(name,str) or not _NAME.fullmatch(name) or (namespace and not _NAME.fullmatch(namespace)):
                    raise ValueError('Salesforce returned an invalid Permission Set identity.')
                result.append({'fullName': (namespace+'__' if namespace else '')+name, 'label': row.get('Label')})
            return result

        fields={'ApexClass':('ApexClass','Name'),'ApexTrigger':('ApexTrigger','Name'),
            'LightningComponentBundle':('LightningComponentBundle','DeveloperName'),'Flow':('FlowDefinition','DeveloperName')}
        if kind not in fields:raise ValueError('Unsupported API component inventory type.')
        table,name=fields[kind]
        rows=self.query(f'SELECT {name}, NamespacePrefix FROM {table}',tooling=True)['records']
        names=[]
        for row in rows:
            value=row.get(name);namespace=row.get('NamespacePrefix')
            if not isinstance(value,str) or not _NAME.fullmatch(value) or (namespace and (not isinstance(namespace,str) or not _NAME.fullmatch(namespace))):
                raise HTTPException(502,'Salesforce component inventory contained an invalid identity.')
            names.append({'fullName':(namespace+'__' if namespace else '')+value})
        return names

    def enrich_validation_rules(self,context):
        context=deepcopy(context);objects=context.get('objects',[])
        if len(objects)>10:raise ValueError('Validation-rule discovery exceeds the object scope.')
        def read_object(obj):
            name=obj['name']
            if not _NAME.fullmatch(name):raise ValueError('Invalid validation-rule owner API name.')
            rows=self.query("SELECT Id, ValidationName FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '"+name+"'",tooling=True)['records']
            if len(rows)>200:raise ValueError('More than 200 validation rules in the requested object scope.')
            rules=[]
            for row in rows:
                ident,rule_name=row.get('Id'),row.get('ValidationName')
                if not isinstance(ident,str) or not _ID.fullmatch(ident) or not isinstance(rule_name,str) or not _NAME.fullmatch(rule_name):
                    raise HTTPException(502,'Salesforce validation-rule inventory is invalid.')
                records=self.query("SELECT Id, Metadata FROM ValidationRule WHERE Id = '"+ident+"'",tooling=True)['records']
                if len(records)!=1 or records[0].get('Id')!=ident or not isinstance(records[0].get('Metadata'),dict):
                    raise HTTPException(502,'Validation-rule metadata retrieval was incomplete.')
                metadata=records[0]['Metadata']
                if not isinstance(metadata.get('active'),bool):raise HTTPException(502,'Validation-rule active flag was not returned.')
                if metadata['active']:
                    if not metadata.get('errorConditionFormula') or not metadata.get('errorMessage'):
                        raise HTTPException(502,'Active validation rule is missing its formula or error message.')
                    rules.append({**{k:metadata.get(k) for k in ('active','errorConditionFormula','errorMessage','errorDisplayField','description')},'fullName':name+'.'+rule_name})
            return rules
        with ThreadPoolExecutor(max_workers=4) as pool:
            for obj,rules in zip(objects,pool.map(read_object,objects)):obj['validationRules']=rules
        context['validationRuleDiscovery']={'status':'complete','objects':sorted(o['name'] for o in objects),
            'activeRuleCount':sum(len(o['validationRules']) for o in objects),'transport':'api',
            'otherAutomation':'Triggers, Flows and related objects outside this scope are not inspected.'}
        return context


def connected_api(metadata):
    api=getattr(metadata,'api',None)
    return api if isinstance(api,SalesforceApiClient) else None
