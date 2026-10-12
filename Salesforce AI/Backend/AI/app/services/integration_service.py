"""Per-account integration settings encrypted with a server-owned key."""
import json
import os
import time
from threading import Lock

_key_lock=Lock()
from pathlib import Path
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException


def cipher():
    from cryptography.fernet import Fernet
    configured=os.getenv('APP_ENCRYPTION_KEY','').strip()
    if configured:
        try:return Fernet(configured.encode())
        except (ValueError,TypeError):raise HTTPException(503,'APP_ENCRYPTION_KEY must be a valid Fernet key.') from None
    from Backend.AI.app.account_api import DB
    path=Path(DB).parent/'integration-encryption.key'
    path.parent.mkdir(parents=True,exist_ok=True)
    with _key_lock:
        try:
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor,'wb') as file:file.write(Fernet.generate_key())
        return Fernet(path.read_bytes())


def load_settings(user_id,kind):
    from Backend.AI.app.account_api import db
    with db() as c:row=c.execute('SELECT payload FROM integrations WHERE user_id=? AND kind=?',(user_id,kind)).fetchone()
    if not row:return None
    try:return json.loads(cipher().decrypt(row['payload'].encode()))
    except Exception:
        raise HTTPException(503,'Saved integration settings cannot be decrypted. Restore the server encryption key or save the integration again.') from None


def save_settings(user_id,kind,value):
    from Backend.AI.app.account_api import db
    encrypted=cipher().encrypt(json.dumps(value).encode()).decode()
    with db() as c:c.execute('INSERT OR REPLACE INTO integrations VALUES(?,?,?)',(user_id,kind,encrypted))


def ai_settings(user_id=None):
    saved=load_settings(user_id,'ai') if user_id else None
    provider=os.getenv('AI_PROVIDER','mock').lower()
    prefix={'anthropic':'ANTHROPIC','openai':'OPENAI','gemini':'GEMINI'}.get(provider,'ANTHROPIC')
    return saved or {'provider':provider,'model':os.getenv(prefix+'_MODEL',''),'api_key':os.getenv(prefix+'_API_KEY',''),'source':'server'}


def verify_ai(user_id,api_key,model,provider='anthropic'):
    if provider not in {'anthropic','openai','gemini'}:raise HTTPException(422,'Choose Claude, OpenAI or Gemini.')
    current=ai_settings(user_id)
    key=api_key.strip() or (current.get('api_key','') if current.get('provider')==provider else '')
    model=model.strip()
    if not key or not model:raise HTTPException(422,'Provide a key for the selected provider and a model ID.')
    if provider=='gemini':model=model.removeprefix('models/')
    try:
        if provider=='anthropic':
            import anthropic
            client=anthropic.Anthropic(api_key=key,timeout=20,max_retries=0)
            supported=[entry.id for entry in client.models.list()]
            if model not in supported:raise HTTPException(422,'Model is not available to this API key.')
        else:
            from Backend.AI.app.providers.rest_provider import RestProvider
            RestProvider(provider,key,model,max_tokens=1024).generate('Reply with the single word OK.','Connection verification.')
    except HTTPException:raise
    except (RuntimeError,ValueError) as error:
        raise HTTPException(422,str(error)) from None
    except Exception:
        raise HTTPException(502,'Provider verification failed. Check key, model access, billing and connectivity.') from None
    settings={'provider':provider,'api_key':key,'model':model,'verifiedAt':time.time(),'source':'account'}
    save_settings(user_id,'ai',settings)
    return public_ai(settings)


def public_ai(settings):
    return {'provider':settings.get('provider'),'model':settings.get('model',''),
            'configured':bool(settings.get('api_key')),'verifiedAt':settings.get('verifiedAt'),
            'source':settings.get('source','account')}


def jira_site(value):
    value=value.strip().rstrip('/')
    parsed=urlparse(value)
    if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.atlassian.net') or parsed.port or parsed.path or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(422,'Enter your Jira Cloud site, for example https://your-team.atlassian.net.')
    return value


def jira_get(settings,path,params=None):
    try:
        with httpx.Client(timeout=20,follow_redirects=False,auth=(settings['email'],settings['api_token'])) as client:
            response=client.get(jira_site(settings['site'])+path,params=params,headers={'Accept':'application/json'})
    except httpx.HTTPError:
        raise HTTPException(502,'Jira could not be reached. Retry when connectivity is restored.') from None
    if response.status_code in (401,403):raise HTTPException(409,'Jira access was denied. Check your account, API token and permissions.')
    if response.status_code!=200:raise HTTPException(502,'Jira could not complete this request. Check site access and retry.')
    try:return response.json()
    except ValueError:raise HTTPException(502,'Jira returned an unreadable response.') from None


def verify_jira(user_id,site,email,api_token):
    previous=load_settings(user_id,'jira') or {}
    settings={'site':jira_site(site),'email':email.strip(),'api_token':api_token.strip() or previous.get('api_token','')}
    if not settings['email'] or not settings['api_token']:raise HTTPException(422,'Provide your Atlassian email and API token.')
    identity=jira_get(settings,'/rest/api/3/myself')
    if not identity.get('accountId'):raise HTTPException(502,'Jira did not return an authenticated account.')
    settings.update(verifiedAt=time.time(),displayName=identity.get('displayName','Jira user'))
    save_settings(user_id,'jira',settings)
    return public_jira(settings)


def public_jira(settings):
    return {'configured':bool(settings),'site':(settings or {}).get('site',''),
            'email':(settings or {}).get('email',''),'displayName':(settings or {}).get('displayName',''),
            'verifiedAt':(settings or {}).get('verifiedAt')}


def jira_stories(user_id):
    settings=load_settings(user_id,'jira')
    if not settings:raise HTTPException(409,'Connect Jira in Settings first.')
    response=jira_get(settings,'/rest/api/3/search/jql',{'jql':'assignee = currentUser() ORDER BY updated DESC','maxResults':20,'fields':'summary,description,status,priority,issuetype'})
    def text(node):
        if not isinstance(node,dict):return ''
        return node.get('text','')+' '.join(text(child) for child in node.get('content',[]))+'\n'
    return [{'key':item['key'],'summary':item.get('fields',{}).get('summary',''),
             'description':text(item.get('fields',{}).get('description')).strip(),
             'status':item.get('fields',{}).get('status',{}).get('name',''),
             'priority':(item.get('fields',{}).get('priority') or {}).get('name',''),
             'issueType':(item.get('fields',{}).get('issuetype') or {}).get('name',''),
             'url':settings['site']+'/browse/'+item['key']} for item in response.get('issues',[])]
