"""App accounts and Salesforce OAuth. One server process; SQLite persistence."""
import base64, hashlib, hmac, json, os, re, secrets, sqlite3, time
from typing import Literal
from contextvars import ContextVar
from threading import Lock
from pathlib import Path
from urllib.parse import urlencode, urlparse
import httpx
from dotenv import load_dotenv
# Resolve the project configuration independently of the terminal directory.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=ENV_FILE, encoding='utf-8-sig', override=False)
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from Backend.AI.app.services.oauth_connection import OAuthConnectionInput, connection_config, encrypt_config, decrypt_config

intelligence_lock = Lock()
current_org = ContextVar('current_org', default=None)
current_account = ContextVar('current_account', default=None)
def target_org():
    value = current_org.get()
    if not value: raise HTTPException(409, 'Connect a Salesforce org first.')
    return value
DB = Path(os.getenv('APP_DATABASE', '.app-data/accounts.sqlite3'))
DB.parent.mkdir(parents=True, exist_ok=True)
class AppConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

SCHEMA = """
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,name TEXT,salt TEXT,password TEXT);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT,expires REAL);
    CREATE TABLE IF NOT EXISTS org_tokens(user_id TEXT,org_id TEXT,payload TEXT NOT NULL,PRIMARY KEY(user_id,org_id));
    CREATE TABLE IF NOT EXISTS orgs(id TEXT PRIMARY KEY,user_id TEXT,name TEXT,type TEXT,username TEXT,instance TEXT);
    CREATE TABLE IF NOT EXISTS oauth(state TEXT PRIMARY KEY,user_id TEXT,session TEXT,host TEXT,verifier TEXT,expires REAL);
    CREATE TABLE IF NOT EXISTS integrations(user_id TEXT,kind TEXT,payload TEXT,PRIMARY KEY(user_id,kind));
    CREATE TABLE IF NOT EXISTS repair_tickets(id TEXT PRIMARY KEY,user_id TEXT,org_id TEXT,payload TEXT,created REAL);
    CREATE TABLE IF NOT EXISTS workflow_events(user_id TEXT,org_id TEXT,plan_id TEXT,signature TEXT,PRIMARY KEY(user_id,org_id,plan_id));
    CREATE TABLE IF NOT EXISTS evaluation_events(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,org_id TEXT NOT NULL,plan_id TEXT,kind TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS evaluation_events_scope ON evaluation_events(user_id,org_id,created);
    CREATE TABLE IF NOT EXISTS background_jobs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,org_id TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,result TEXT,created REAL NOT NULL,updated REAL NOT NULL,request_key TEXT NOT NULL,UNIQUE(user_id,org_id,request_key));
    CREATE INDEX IF NOT EXISTS background_jobs_due ON background_jobs(state,created);
    CREATE TABLE IF NOT EXISTS monitor_jobs(plan_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,org_id TEXT NOT NULL,next_poll REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS workspace_packages(id TEXT PRIMARY KEY,user_id TEXT,org_id TEXT,payload TEXT);
    CREATE TABLE IF NOT EXISTS workspace_conversations(id TEXT PRIMARY KEY,user_id TEXT,org_id TEXT,title TEXT,updated REAL);
    CREATE TABLE IF NOT EXISTS workspace_messages(id TEXT PRIMARY KEY,conversation_id TEXT,role TEXT,content TEXT,kind TEXT,plan_id TEXT,context TEXT,created REAL);
    CREATE INDEX IF NOT EXISTS workspace_messages_conversation ON workspace_messages(conversation_id,created);
    CREATE TABLE IF NOT EXISTS workspace_chats(id TEXT PRIMARY KEY,user_id TEXT,org_id TEXT,requirement TEXT,updated REAL);
    CREATE TABLE IF NOT EXISTS org_cache_epochs(user_id TEXT,org_id TEXT,epoch INTEGER NOT NULL,PRIMARY KEY(user_id,org_id));
    CREATE TABLE IF NOT EXISTS org_intelligence_cache(org_id TEXT,user_id TEXT,payload TEXT,synced REAL,PRIMARY KEY(org_id,user_id));
    CREATE TABLE IF NOT EXISTS org_intelligence_history(org_id TEXT,user_id TEXT,bucket INTEGER,created REAL,api_used REAL,api_limit REAL,PRIMARY KEY(org_id,user_id,bucket));
    CREATE TABLE IF NOT EXISTS org_identity(org_id TEXT PRIMARY KEY,salesforce_id TEXT);
    CREATE TABLE IF NOT EXISTS org_health(org_id TEXT PRIMARY KEY,status TEXT,checked REAL,message TEXT);
    CREATE TABLE IF NOT EXISTS oauth_clients(state TEXT PRIMARY KEY,user_id TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS oauth_reconnect(state TEXT PRIMARY KEY,org_id TEXT);
    CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY,count INTEGER,expires REAL);
    CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,user_id TEXT,org_id TEXT);
    CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL,org_id TEXT,plan_id TEXT,kind TEXT NOT NULL,title TEXT NOT NULL,summary TEXT,status TEXT,created REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS activity_owner ON activity(user_id,org_id,created);
    """

def db():
    from Backend.AI.app.services.app_database import postgres_enabled, connect_postgres
    if postgres_enabled():
        return connect_postgres(SCHEMA)
    c=sqlite3.connect(DB, timeout=30, factory=AppConnection);c.row_factory=sqlite3.Row
    c.executescript(SCHEMA)
    return c
router=APIRouter(prefix='/api',tags=['Accounts and orgs'])
class Credentials(BaseModel):
    email: str=Field(min_length=3,max_length=254)
    password: str=Field(min_length=10,max_length=256)
    name: str=Field(default='',max_length=100)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password,salt): return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def user(request):
    token=request.cookies.get('app_session','')
    with db() as c:
        row=c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',(digest(token),time.time())).fetchone()
    if not row: raise HTTPException(401,'Please sign in.')
    return dict(row)
def public(u):return {k:u[k] for k in ('id','email','name')}
def throttle(request, email):
    key=digest((request.client.host if request.client else 'unknown')+':'+email.lower())
    with db() as c:
        c.execute('DELETE FROM attempts WHERE expires<?',(time.time(),))
        c.execute('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,time.time()+900))
        row=c.execute('SELECT count FROM attempts WHERE key=?',(key,)).fetchone()
    if row['count']>15:raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')
def session_response(u):
    token=secrets.token_urlsafe(32)
    with db() as c:c.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),u['id'],time.time()+86400))
    response=JSONResponse(public(u));response.set_cookie('app_session',token,httponly=True,samesite='lax',secure=os.getenv('APP_COOKIE_SECURE','false')=='true',max_age=86400,path='/')
    return response
@router.post('/auth/register')
def register(data:Credentials,request:Request):
    check_origin(request)
    throttle(request,data.email)
    email=data.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise HTTPException(422,'Enter a valid email.')
    salt=secrets.token_hex(16);u={'id':secrets.token_hex(16),'email':email,'name':data.name.strip() or email.split('@')[0]}
    try:
        with db() as c:c.execute('INSERT INTO users VALUES(?,?,?,?,?)',(u['id'],email,u['name'],salt,password_hash(data.password,salt)))
    except sqlite3.IntegrityError:raise HTTPException(409,'An account already exists for this email.')
    return session_response(u)
@router.post('/auth/login')
def login(data:Credentials,request:Request):
    check_origin(request)
    throttle(request,data.email)
    with db() as c: row=c.execute('SELECT * FROM users WHERE email=?',(data.email.strip().lower(),)).fetchone()
    salt=row['salt'] if row else '00'*16
    candidate=password_hash(data.password,salt)
    if not row or not hmac.compare_digest(row['password'],candidate):raise HTTPException(401,'Email or password is incorrect.')
    return session_response(dict(row))
@router.get('/auth/me')
def me(request:Request):return public(user(request))
@router.post('/auth/logout')
def logout(request:Request):
    check_origin(request)
    with db() as c:c.execute('DELETE FROM sessions WHERE token=?',(digest(request.cookies.get('app_session','')),))
    response=JSONResponse({'ok':True});response.delete_cookie('app_session',path='/');return response
@router.get('/orgs')
def orgs(request:Request):
    u=user(request)
    with db() as c:
        rows=c.execute('SELECT o.*, h.status, h.checked, h.message FROM orgs o LEFT JOIN org_health h ON o.id=h.org_id WHERE o.user_id=? ORDER BY o.id DESC',(u['id'],)).fetchall()
    return [{**{k:r[k] for k in ('id','name','type','username','instance')},
             'status':r['status'] or 'Not checked', 'checkedAt':r['checked'],
             'connectionMessage':r['message'] or ''} for r in rows]


def owned_org(request, org_id):
    u=user(request)
    with db() as c:
        row=c.execute('SELECT * FROM orgs WHERE id=? AND user_id=?',(org_id,u['id'])).fetchone()
    if not row:raise HTTPException(404,'Connection not found.')
    return u, row


@router.post('/orgs/{org_id}/verify')
def verify_org(request:Request,org_id:str):
    check_origin(request)
    _, row=owned_org(request,org_id)
    with db() as c:
        saved=c.execute('SELECT salesforce_id FROM org_identity WHERE org_id=?',(org_id,)).fetchone()
    expected_id=saved['salesforce_id'] if saved else row['name']
    from Backend.AI.app.services.salesforce_api_client import SalesforceApiClient
    from Backend.AI.app.services.flow_generator import api_version
    status='Check failed';message='Unable to verify Salesforce. Check connectivity and API permissions, then retry.'
    try:
        api=SalesforceApiClient(row['user_id'],org_id,api_version(PROJECT_ROOT))
        records=api.query('SELECT Id, Name FROM Organization LIMIT 1')['records']
        if len(records)!=1 or not isinstance(records[0],dict) or not re.fullmatch(r'00D[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',str(records[0].get('Id',''))):
            raise HTTPException(502,'Salesforce organization identity could not be verified.')
        identity=records[0]
        if re.fullmatch(r'00D[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',expected_id or '') and identity['Id'][:15]!=expected_id[:15]:
            status='Reconnect required';message='Salesforce returned a different organization. Reconnect this saved org.'
        else:
            status='Connected';message='Live Salesforce API check succeeded.'
            with db() as c:
                if c.execute('SELECT id FROM orgs WHERE id=? AND user_id=?',(org_id,row['user_id'])).fetchone():
                    c.execute('INSERT OR REPLACE INTO org_identity VALUES(?,?)',(org_id,identity['Id']))
                    if identity.get('Name'):c.execute('UPDATE orgs SET name=? WHERE id=? AND user_id=?',(identity['Name'],org_id,row['user_id']))
    except HTTPException as error:
        status='Reconnect required' if error.status_code==409 else 'Check failed'
        message=str(error.detail)
    checked=time.time()
    with db() as c:
        # Do not recreate health entries for a concurrently removed connection.
        if c.execute('SELECT id FROM orgs WHERE id=? AND user_id=?',(org_id,row['user_id'])).fetchone():
            c.execute('INSERT OR REPLACE INTO org_health VALUES(?,?,?,?)',(org_id,status,checked,message))
    return {'id':org_id,'status':status,'checkedAt':checked,'connectionMessage':message}


@router.delete('/orgs/{org_id}')
def remove_org(request:Request,org_id:str):
    check_origin(request);u,_=owned_org(request,org_id)
    with db() as c:
        c.execute('DELETE FROM org_tokens WHERE org_id=? AND user_id=?',(org_id,u['id']))
        c.execute('DELETE FROM orgs WHERE id=? AND user_id=?',(org_id,u['id']))
        c.execute('DELETE FROM org_health WHERE org_id=?',(org_id,))
        c.execute('DELETE FROM org_identity WHERE org_id=?',(org_id,))
        c.execute('DELETE FROM org_intelligence_cache WHERE org_id=? AND user_id=?',(org_id,u['id']))
        c.execute('DELETE FROM oauth WHERE state IN (SELECT state FROM oauth_reconnect WHERE org_id=?)',(org_id,))
        c.execute('DELETE FROM oauth_reconnect WHERE org_id=?',(org_id,))
    # Keep history. Removing an application connection does not revoke Salesforce grants.
    record_activity(u['id'],org_id,None,'disconnected','Salesforce connection removed')
    return {'ok':True}


def intelligence_snapshot(request,org_id,force=False):
    from .services.org_intelligence_service import collect_intelligence, Unavailable
    u,org=owned_org(request,org_id)
    # Single-process backend: prevent duplicate snapshots and concurrent token refreshes.
    with intelligence_lock:
        with db() as c:
            cached=c.execute('SELECT * FROM org_intelligence_cache WHERE org_id=? AND user_id=?',(org_id,u['id'])).fetchone()
            identity=c.execute('SELECT salesforce_id FROM org_identity WHERE org_id=?',(org_id,)).fetchone()
            version=c.execute('SELECT epoch FROM org_cache_epochs WHERE user_id=? AND org_id=?',(u['id'],org_id)).fetchone()
            cache_epoch=version['epoch'] if version else 0
        if cached and not force and time.time()-cached['synced']<300:
            payload=json.loads(cached['payload'])
        else:
            expected=identity['salesforce_id'] if identity else (org['name'] if re.fullmatch(r'00D[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',org['name'] or '') else None)
            try:
                payload=collect_intelligence(dict(org),expected)
            except HTTPException as error:
                if error.status_code==409:
                    with db() as c:c.execute('INSERT OR REPLACE INTO org_health VALUES(?,?,?,?)',(org_id,'Reconnect required',time.time(),error.detail))
                raise
            except (Unavailable,httpx.HTTPError,ValueError,KeyError,TypeError):
                raise HTTPException(502,'Could not read Salesforce intelligence. Check connectivity and retry.') from None
            now=payload['syncedAt']
            with db() as c:
                if not c.execute('SELECT id FROM orgs WHERE id=? AND user_id=?',(org_id,u['id'])).fetchone():
                    raise HTTPException(404,'Connection removed during synchronization.')
                version=c.execute('SELECT epoch FROM org_cache_epochs WHERE user_id=? AND org_id=?',(u['id'],org_id)).fetchone()
                if (version['epoch'] if version else 0)==cache_epoch:
                    c.execute('INSERT OR REPLACE INTO org_intelligence_cache VALUES(?,?,?,?)',(org_id,u['id'],json.dumps(payload),now))
                c.execute('INSERT OR REPLACE INTO org_identity VALUES(?,?)',(org_id,payload['organization']['id']))
                c.execute('UPDATE orgs SET name=? WHERE id=? AND user_id=?',(payload['organization']['name'],org_id,u['id']))
                c.execute('INSERT OR REPLACE INTO org_health VALUES(?,?,?,?)',(org_id,'Connected',now,'Live org intelligence synchronized.'))
                api=(payload['metrics'].get('limits') or {}).get('DailyApiRequests')
                if api:
                    c.execute('INSERT OR REPLACE INTO org_intelligence_history VALUES(?,?,?,?,?,?)',(org_id,u['id'],int(now//3600),now,api['used'],api['limit']))
                c.execute('DELETE FROM org_intelligence_history WHERE created<?',(now-30*86400,))
        with db() as c:
            history=c.execute('SELECT created,api_used,api_limit FROM org_intelligence_history WHERE org_id=? AND user_id=? AND created>? ORDER BY created',(org_id,u['id'],time.time()-86400)).fetchall()
            events=c.execute('SELECT id,kind,title,summary,status,created FROM activity WHERE org_id=? AND user_id=? ORDER BY created DESC,id DESC LIMIT 8',(org_id,u['id'])).fetchall()
        return {**payload,'history':[dict(r) for r in history], 'activity':[dict(r) for r in events], 'refreshIntervalSeconds':300}


@router.get('/orgs/{org_id}/intelligence')
def get_intelligence(request:Request,org_id:str):
    return intelligence_snapshot(request,org_id)


@router.post('/orgs/{org_id}/intelligence/sync')
def sync_intelligence(request:Request,org_id:str):
    check_origin(request)
    result = intelligence_snapshot(request,org_id,force=True)
    from Backend.AI.app.services.planning_performance import planning_cache
    planning_cache.invalidate(user(request)['id'], org_id)
    return result

def configured_url(name, origin_only=False):
    value = os.getenv(name, '').strip().rstrip('/')
    if not value:
        raise HTTPException(503, f'{name} is missing. Configure the backend and restart it.')
    parsed = urlparse(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise HTTPException(503, f'{name} must be a valid HTTP or HTTPS URL.')
    if origin_only and parsed.path:
        raise HTTPException(503, f'{name} must contain only the scheme, hostname and port.')
    return value


def check_origin(request):
    expected = configured_url('APP_PUBLIC_URL', origin_only=True)
    origin = request.headers.get('origin')
    if origin and origin != expected:
        raise HTTPException(
            403,
            f'Request origin {origin!r} does not match APP_PUBLIC_URL {expected!r}. '
            'Open the configured URL, or update the backend configuration and restart it.'
        )


def client():
    value = os.getenv('SF_OAUTH_CLIENT_ID', '').strip()
    if not value:
        raise HTTPException(503, 'SF_OAUTH_CLIENT_ID is missing. Configure the backend OAuth client and restart it.')
    return value


def callback():
    value = configured_url('SF_OAUTH_CALLBACK_URL')
    public_url = configured_url('APP_PUBLIC_URL', origin_only=True)
    if value != public_url + '/api/orgs/callback':
        raise HTTPException(503, 'SF_OAUTH_CALLBACK_URL must equal APP_PUBLIC_URL followed by /api/orgs/callback. Also register this exact URL in Salesforce.')
    return value

@router.post('/orgs/connect')
async def connect(request:Request,environment:str='production',reconnect_id:str=''):
    check_origin(request);u=user(request);redirect_uri=callback();config=None;body=None
    raw=await request.body()
    if len(raw)>4096:raise HTTPException(413,'Connection configuration is too large.')
    if raw:
        try:body=OAuthConnectionInput.model_validate_json(raw)
        except ValueError:raise HTTPException(422,'Provide Consumer Key, Consumer Secret, Salesforce org URL and username. Extra fields are not accepted.') from None
    if reconnect_id:
        _,existing=owned_org(request,reconnect_id)
        environment='sandbox' if existing['type']=='Sandbox' else 'production'
        if body is None:
            from Backend.AI.app.services.salesforce_api_client import load_org_tokens
            config=load_org_tokens(u['id'],reconnect_id).get('oauth_client')
    if environment not in ('production','sandbox'):raise HTTPException(422,'Choose production or sandbox.')
    if body is not None:config=connection_config(body,environment)
    cid=config['client_id'] if config else client()
    host=config['auth_host'] if config else ('https://test.salesforce.com' if environment=='sandbox' else 'https://login.salesforce.com')
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    with db() as c:
        c.execute('INSERT INTO oauth VALUES(?,?,?,?,?,?)',(digest(state),u['id'],digest(request.cookies.get('app_session','')),host,verifier,time.time()+600))
        if config:c.execute('INSERT INTO oauth_clients VALUES(?,?,?)',(digest(state),u['id'],encrypt_config(config)))
        c.execute('DELETE FROM oauth_clients WHERE state NOT IN (SELECT state FROM oauth WHERE expires>?)',(time.time(),))
        if reconnect_id:c.execute('INSERT INTO oauth_reconnect VALUES(?,?)',(digest(state),reconnect_id))
    return {'url':host+'/services/oauth2/authorize?'+urlencode({'response_type':'code','client_id':cid,'redirect_uri':redirect_uri,'scope':'openid api refresh_token','state':state,'code_challenge':challenge,'code_challenge_method':'S256','prompt':'login consent',**({'login_hint':config['username']} if config else {})})}
@router.get('/orgs/callback')
def oauth_callback(request:Request,state:str='',code:str='',error:str=''):
    u=user(request)
    with db() as c:
        row=c.execute('DELETE FROM oauth WHERE state=? AND user_id=? AND session=? AND expires>? RETURNING *',(digest(state),u['id'],digest(request.cookies.get('app_session','')),time.time())).fetchone()
        reconnect=c.execute('SELECT org_id FROM oauth_reconnect WHERE state=?',(digest(state),)).fetchone()
        pending=c.execute('SELECT payload FROM oauth_clients WHERE state=? AND user_id=?',(digest(state),u['id'])).fetchone()
        if row:c.execute('DELETE FROM oauth_clients WHERE state=? AND user_id=?',(digest(state),u['id']))
        if row:c.execute('DELETE FROM oauth_reconnect WHERE state=?',(digest(state),))
    if not row:raise HTTPException(400,'Connection expired or invalid. Try again.')
    if error or not code:return RedirectResponse('/?connection=cancelled',303)
    config=decrypt_config(pending['payload']) if pending else None
    data={'grant_type':'authorization_code','code':code,'client_id':config['client_id'] if config else client(),'redirect_uri':callback(),'code_verifier':row['verifier']}
    secret=config['client_secret'] if config else os.getenv('SF_OAUTH_CLIENT_SECRET','')
    if secret:data['client_secret']=secret
    with httpx.Client(timeout=30,follow_redirects=False) as h:
        result=h.post(row['host']+'/services/oauth2/token',data=data)
        if result.status_code!=200:raise HTTPException(502,'Salesforce authorization failed. Check OAuth app configuration.')
        tokens=result.json()
        from Backend.AI.app.services.salesforce_api_client import instance_url
        if not isinstance(tokens,dict):raise HTTPException(502,'Salesforce returned invalid OAuth credentials.')
        tokens['instance_url']=instance_url(tokens.get('instance_url'))
        if not isinstance(tokens.get('access_token'),str) or not tokens['access_token']:raise HTTPException(502,'Salesforce did not supply an access token.')
        if not tokens.get('refresh_token'):raise HTTPException(502,'Salesforce did not issue a refresh token. Enable refresh_token scope.')
        identity=h.get(tokens['instance_url']+'/services/oauth2/userinfo',headers={'Authorization':'Bearer '+tokens['access_token']})
        if identity.status_code!=200:raise HTTPException(502,'Unable to verify Salesforce identity.')
        info=identity.json()
        if not isinstance(info,dict) or not re.fullmatch(r'00D[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',str(info.get('organization_id',''))) or not isinstance(info.get('preferred_username'),str) or not info['preferred_username']:
            raise HTTPException(502,'Salesforce did not return a complete organization and user identity.')
    if config:
        if info['preferred_username'].lower()!=config['username'].lower() or tokens['instance_url'].lower()!=config['expected_instance'].lower():
            raise HTTPException(409,'Authorized Salesforce user or org does not match the entered username and org URL. Start a new connection.')
        tokens['oauth_client']=config
    alias='app_'+secrets.token_hex(16)
    if reconnect:
        _,existing=owned_org(request,reconnect['org_id'])
        with db() as c:saved=c.execute('SELECT salesforce_id FROM org_identity WHERE org_id=?',(existing['id'],)).fetchone()
        if saved and info.get('organization_id','')[:15]!=saved['salesforce_id'][:15]:
            raise HTTPException(409,'Sign in to the same Salesforce organization to reconnect.')
        if info.get('preferred_username','').lower()!=existing['username'].lower() or tokens['instance_url'].rstrip('/').lower()!=existing['instance'].rstrip('/').lower():
            raise HTTPException(409,'Sign in to the same Salesforce user and org to reconnect. Use Connect an organization for a different org.')
        alias=existing['id']
    with db() as c:
        if reconnect and not c.execute('SELECT id FROM orgs WHERE id=? AND user_id=?',(alias,u['id'])).fetchone():
            raise HTTPException(409,'This connection was removed. Start a new connection.')
        c.execute('INSERT OR REPLACE INTO orgs VALUES(?,?,?,?,?,?)',(alias,u['id'],info.get('organization_id','Salesforce org'),'Sandbox' if (config and config['environment']=='sandbox') or row['host'].startswith('https://test.') else 'Production / Developer',info.get('preferred_username',''),tokens['instance_url']))
        c.execute('INSERT OR REPLACE INTO org_identity VALUES(?,?)',(alias,info.get('organization_id','')))
        c.execute('INSERT OR REPLACE INTO org_health VALUES(?,?,?,?)',(alias,'Connected',time.time(),'Salesforce identity verified during authorization.'))
        from Backend.AI.app.services.salesforce_api_client import encrypt_org_tokens
        encrypted=encrypt_org_tokens(tokens,row['host'])
        c.execute('INSERT OR REPLACE INTO org_tokens VALUES(?,?,?)',(u['id'],alias,encrypted))
    record_activity(u['id'],alias,None,'connected','Salesforce org connected',info.get('preferred_username',''))
    return RedirectResponse('/?'+urlencode({'connection':'success','org':alias}),303)

def record_activity(user_id, org_id, plan_id, kind, title, summary='', status='completed'):
    if kind in ('deployed','connected','disconnected'):
        from Backend.AI.app.services.planning_performance import planning_cache
        planning_cache.invalidate(user_id, org_id)
    with db() as c:
        if kind in ('deployed','connected','disconnected'):
            c.execute('DELETE FROM org_intelligence_cache WHERE org_id=? AND user_id=?',(org_id,user_id))
        c.execute('INSERT INTO activity(user_id,org_id,plan_id,kind,title,summary,status,created) VALUES(?,?,?,?,?,?,?,?)',
                  (user_id,org_id,plan_id,kind,title,str(summary)[:300],status,time.time()))

@router.get('/home/overview')
def home_overview(request:Request,org_id:str|None=None,limit:int=8):
    u=user(request)
    if not 1<=limit<=100:raise HTTPException(422,'Activity limit must be between 1 and 100.')
    with db() as c:
        org_count=c.execute('SELECT COUNT(*) FROM orgs WHERE user_id=?',(u['id'],)).fetchone()[0]
        if org_id and not c.execute('SELECT id FROM orgs WHERE user_id=? AND id=?',(u['id'],org_id)).fetchone():
            raise HTTPException(403,'This org is not connected to your account.')
        clause='user_id=?'+(' AND org_id=?' if org_id else '')
        params=(u['id'],org_id) if org_id else (u['id'],)
        plans=c.execute('SELECT COUNT(*) FROM plans WHERE '+clause,params).fetchone()[0]
        approved=c.execute("SELECT COUNT(DISTINCT plan_id) FROM activity WHERE "+clause+" AND kind='approved'",params).fetchone()[0]
        deployed=c.execute("SELECT COUNT(DISTINCT plan_id) FROM activity WHERE "+clause+" AND kind='deployed'",params).fetchone()[0]
        total=c.execute('SELECT COUNT(*) FROM activity WHERE '+clause,params).fetchone()[0]
        rows=c.execute('SELECT * FROM activity WHERE '+clause+' ORDER BY created DESC,id DESC LIMIT ?',(*params,limit)).fetchall()
    return {'stats':{'connectedOrgs':org_count,'plans':plans,'approved':approved,'deployed':deployed},
            'activity':[{'id':r['id'],'orgId':r['org_id'],'planId':r['plan_id'],'type':r['kind'],'title':r['title'],
                         'summary':r['summary'],'status':r['status'],'createdAt':r['created']} for r in rows],
            'activityTotal':total,'checkedAt':time.time()}

def record_workflow_response(u,org,plan_id,path,payload,status_code):
    action=path.rsplit('/',1)[-1]
    summary=payload.get('plan',{}).get('summary','') if isinstance(payload.get('plan'),dict) else ''
    if status_code>=400:
        record_activity(u['id'],org,plan_id,'failed',action.replace('-',' ').capitalize()+' needs attention',status='failed')
        return
    if path=='/api/plan' and payload.get('backgroundJob'):return
    if path=='/api/plan':kind,title='generated','Implementation generated'
    elif action=='approve':kind,title='approved','Plan approved for deployment'
    elif action=='reject':kind,title='rejected','Plan rejected'
    elif action in ('deploy','validate','report'):
        state=payload.get('state')
        if state=='deployed':kind,title='deployed','Deployment completed in Salesforce'
        elif state=='validated':kind,title='validated','Salesforce validation passed'
        elif state=='failed':kind,title='failed','Salesforce operation failed'
        elif state in ('pending','running','unknown'):
            kind,title='pending','Salesforce operation awaiting confirmation'
        else:kind,title='pending','Salesforce operation requested'
        signature=json.dumps([payload.get('jobId'),state,payload.get('operation')])
        with db() as c:
            old=c.execute('SELECT signature FROM workflow_events WHERE user_id=? AND org_id=? AND plan_id=?',(u['id'],org,plan_id)).fetchone()
            if old and old['signature']==signature:return
            c.execute('INSERT OR REPLACE INTO workflow_events VALUES(?,?,?,?)',(u['id'],org,plan_id,signature))
        record_activity(u['id'],org,plan_id,kind,title,summary,status=state or 'pending')
        return
    else:kind,title='reviewed','Implementation review updated'
    record_activity(u['id'],org,plan_id,kind,title,summary)

async def account_guard(request,call_next):
    path=request.url.path
    if not path.startswith('/api/') or path.startswith('/api/auth/') or path.startswith('/api/orgs'):
        return await call_next(request)
    try:
        u=user(request)
        if request.method not in ('GET','HEAD','OPTIONS'):check_origin(request)
        # Only the unified workspace workflow is enabled for signed-in accounts.
        if path.startswith('/api/apex/') or path.startswith('/api/lwc/'):raise HTTPException(403,'Use the unified workspace workflow.')
        match=re.match(r'/api/plans/([^/]+)',path)
        org=None
        if match:
            with db() as c:row=c.execute('SELECT org_id FROM plans WHERE id=? AND user_id=?',(match[1],u['id'])).fetchone()
            if not row:raise HTTPException(404,'Plan not found.')
            org=row['org_id']
        elif path in ('/api/plan', '/api/workspace/respond'):
            body=await request.json();org=body.get('target_org')
        else:org=request.headers.get('x-org-id')
        if org:
            with db() as c:row=c.execute('SELECT id FROM orgs WHERE id=? AND user_id=?',(org,u['id'])).fetchone()
            if not row:raise HTTPException(403,'This org is not connected to your account.')
        context=current_org.set(org)
        account_context=current_account.set(u['id'])
        try:
            if match and not path.endswith('/status'):
                from Backend.AI.app.main import restore_workspace_package
                from starlette.concurrency import run_in_threadpool
                await run_in_threadpool(restore_workspace_package,match[1],u['id'],org)
            response=await call_next(request)
            tracked = request.method=='POST' and (path=='/api/plan' or
                (match and path.rsplit('/',1)[-1] in {'approve','reject','deploy','validate','report','generate-metadata','layout-selections'}))
            if tracked:
                content=b''.join([part async for part in response.body_iterator])
                try:payload=json.loads(content)
                except (ValueError,TypeError):
                    from starlette.responses import Response
                    return Response(content,status_code=response.status_code,headers=dict(response.headers))
                plan_id=match[1] if match else (payload.get('id') or payload.get('planId') or payload.get('plan',{}).get('id'))
                if path=='/api/plan' and response.status_code<300 and plan_id:
                    with db() as c:c.execute('INSERT OR REPLACE INTO plans VALUES(?,?,?)',(plan_id,u['id'],org))
                if org:
                    record_workflow_response(u,org,plan_id,path,payload,response.status_code)
                    if response.status_code<300 and payload.get('requirement') and plan_id:
                        save_chat(u['id'],org,plan_id,payload['requirement'])
                return JSONResponse(payload,status_code=response.status_code)
            return response
        finally:
            current_org.reset(context)
            current_account.reset(account_context)
    except HTTPException as exc:return JSONResponse({'detail':exc.detail},status_code=exc.status_code)


def save_chat(user_id,org_id,plan_id,requirement):
    with db() as c:
        c.execute('INSERT OR REPLACE INTO workspace_chats VALUES(?,?,?,?,?)',(plan_id,user_id,org_id,requirement,time.time()))


@router.get('/orgs/{org_id}/chats')
def workspace_chats(request:Request,org_id:str):
    u,_=owned_org(request,org_id)
    with db() as c:rows=c.execute('SELECT id,requirement,updated FROM workspace_chats WHERE user_id=? AND org_id=? AND NOT EXISTS (SELECT 1 FROM workspace_messages m JOIN workspace_conversations t ON t.id=m.conversation_id WHERE m.plan_id=workspace_chats.id AND t.user_id=workspace_chats.user_id AND t.org_id=workspace_chats.org_id) ORDER BY updated DESC LIMIT 50',(u['id'],org_id)).fetchall()
    return [{'id':r['id'],'requirement':r['requirement'],'updated':r['updated'],'targetOrg':org_id,'kind':'default'} for r in rows]


class ConversationRequest(BaseModel):
    title:str=Field(min_length=1,max_length=300)


class ConversationMessageRequest(BaseModel):
    role:Literal['user','assistant']
    content:str=Field(min_length=1,max_length=20000)
    kind:Literal['message','clarification','plan','no_change','error']='message'
    plan_id:str|None=Field(default=None,max_length=100)
    context:str=Field(default='',max_length=40000)


def owned_conversation(request,org_id,conversation_id):
    u,_=owned_org(request,org_id)
    with db() as c:
        row=c.execute('SELECT * FROM workspace_conversations WHERE id=? AND user_id=? AND org_id=?',(conversation_id,u['id'],org_id)).fetchone()
    if not row:raise HTTPException(404,'Conversation not found.')
    return u,row


@router.get('/orgs/{org_id}/conversations')
def list_conversations(request:Request,org_id:str):
    u,_=owned_org(request,org_id)
    with db() as c:
        rows=c.execute('SELECT id,title,updated FROM workspace_conversations WHERE user_id=? AND org_id=? ORDER BY updated DESC LIMIT 100',(u['id'],org_id)).fetchall()
    return [dict(row,targetOrg=org_id,kind='conversation',requirement=row['title']) for row in rows]


@router.post('/orgs/{org_id}/conversations')
def create_conversation(request:Request,org_id:str,body:ConversationRequest):
    u,_=owned_org(request,org_id);conversation_id='CHAT-'+secrets.token_hex(12)
    with db() as c:
        c.execute('INSERT INTO workspace_conversations VALUES(?,?,?,?,?)',(conversation_id,u['id'],org_id,body.title,time.time()))
    return {'id':conversation_id,'title':body.title,'requirement':body.title,'targetOrg':org_id,'kind':'conversation'}


@router.get('/orgs/{org_id}/conversations/{conversation_id}')
def read_conversation(request:Request,org_id:str,conversation_id:str):
    _,conversation=owned_conversation(request,org_id,conversation_id)
    with db() as c:
        rows=c.execute('SELECT * FROM workspace_messages WHERE conversation_id=? ORDER BY created DESC,id DESC LIMIT 200',(conversation_id,)).fetchall()
    return {'id':conversation_id,'title':conversation['title'],'targetOrg':org_id,'messages':[dict(row) for row in reversed(rows)]}


@router.post('/orgs/{org_id}/conversations/{conversation_id}/messages')
def append_conversation_message(request:Request,org_id:str,conversation_id:str,body:ConversationMessageRequest):
    u,_=owned_conversation(request,org_id,conversation_id)
    message_id=secrets.token_hex(16);created=time.time()
    with db() as c:
        if body.plan_id and not c.execute('SELECT id FROM plans WHERE id=? AND user_id=? AND org_id=?',(body.plan_id,u['id'],org_id)).fetchone():
            raise HTTPException(404,'Plan not found in this org.')
        c.execute('INSERT INTO workspace_messages VALUES(?,?,?,?,?,?,?,?)',(message_id,conversation_id,body.role,body.content,body.kind,body.plan_id,body.context,created))
        c.execute('UPDATE workspace_conversations SET updated=? WHERE id=?',(created,conversation_id))
    return {'id':message_id,'role':body.role,'content':body.content,'kind':body.kind,'plan_id':body.plan_id,'context':body.context,'created':created}


class AISettingsRequest(BaseModel):
    provider:Literal['anthropic','openai','gemini']='anthropic'
    api_key:str=Field(default='',max_length=1000)
    model:str=Field(min_length=1,max_length=200)


class JiraSettingsRequest(BaseModel):
    site:str=Field(min_length=1,max_length=500)
    email:str=Field(min_length=1,max_length=254)
    api_token:str=Field(default='',max_length=2000)


@router.get('/integrations')
def integrations(request:Request):
    from .services.integration_service import ai_settings,public_ai,load_settings,public_jira
    u=user(request)
    return {'ai':public_ai(ai_settings(u['id'])),'jira':public_jira(load_settings(u['id'],'jira'))}


@router.post('/integrations/ai')
async def configure_ai(request:Request):
    from .services.integration_service import verify_ai
    check_origin(request);u=user(request)
    raw=await request.body()
    if len(raw)>4096:raise HTTPException(413,'AI settings are too large.')
    try:settings=AISettingsRequest.model_validate_json(raw)
    except ValueError:raise HTTPException(422,'Provide a supported provider, API key and model ID.') from None
    return verify_ai(u['id'],settings.api_key,settings.model,settings.provider)


@router.post('/integrations/jira')
def configure_jira(request:Request,settings:JiraSettingsRequest):
    from .services.integration_service import verify_jira
    check_origin(request);u=user(request)
    return verify_jira(u['id'],settings.site,settings.email,settings.api_token)


@router.delete('/integrations/{kind}')
def remove_integration(request:Request,kind:str):
    check_origin(request);u=user(request)
    if kind not in ('ai','jira'):raise HTTPException(404,'Integration not found.')
    with db() as c:c.execute('DELETE FROM integrations WHERE user_id=? AND kind=?',(u['id'],kind))
    return {'ok':True}


@router.get('/integrations/jira/stories')
def get_jira_stories(request:Request):
    from .services.integration_service import jira_stories
    return jira_stories(user(request)['id'])
