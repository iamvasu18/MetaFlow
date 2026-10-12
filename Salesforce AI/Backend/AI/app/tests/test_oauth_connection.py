from urllib.parse import urlsplit,parse_qs
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from Backend.AI.app.services.oauth_connection import OAuthConnectionInput,connection_config,auth_host,refresh_credentials
BODY=dict(consumer_key='customer-key-123',consumer_secret='customer-secret',org_url='https://example.my.salesforce.com',username='person@example.com')

@pytest.mark.parametrize('url',['http://example.my.salesforce.com','https://evil.com','https://example.my.salesforce.com.evil.com','https://127.0.0.1','https://example.my.salesforce.com/path','https://u:p@example.my.salesforce.com','https://example.my.salesforce.com:443'])
def test_rejects_invalid_hosts(url):
    with pytest.raises(HTTPException):auth_host(url)

def test_environment_and_specific_org():
    assert connection_config(OAuthConnectionInput(**BODY),'production')['auth_host']==BODY['org_url']
    with pytest.raises(HTTPException):connection_config(OAuthConnectionInput(**BODY),'sandbox')
    with pytest.raises(HTTPException):connection_config(OAuthConnectionInput(**{**BODY,'org_url':'https://login.salesforce.com'}),'production')

def test_custom_refresh_ignores_server(monkeypatch):
    monkeypatch.setenv('SF_OAUTH_CLIENT_ID','wrong')
    assert refresh_credentials({'oauth_client':{'client_id':'own','client_secret':'secret'}})==dict(client_id='own',client_secret='secret')

@pytest.mark.parametrize('wrong_identity',[False,True])
def test_authorization_uses_owned_encrypted_credentials(monkeypatch,tmp_path,wrong_identity):
    from Backend.AI.app import account_api as a
    from Backend.AI.app.services.salesforce_api_client import load_org_tokens
    monkeypatch.setattr(a,'DB',tmp_path/'accounts.sqlite3')
    for k,v in dict(APP_DATABASE_URL='',APP_ENCRYPTION_KEY=Fernet.generate_key().decode(),APP_PUBLIC_URL='https://app.example.com',SF_OAUTH_CALLBACK_URL='https://app.example.com/api/orgs/callback').items():monkeypatch.setenv(k,v)
    monkeypatch.delenv('SF_OAUTH_CLIENT_ID',raising=False)
    monkeypatch.setattr(a,'user',lambda r:{'id':'owner'})
    app=FastAPI();app.include_router(a.router);c=TestClient(app)
    r=c.post('/api/orgs/connect',json=BODY,headers={'Origin':'https://app.example.com'})
    assert r.status_code==200,r.text
    q=parse_qs(urlsplit(r.json()['url']).query)
    assert q['client_id']==[BODY['consumer_key']]
    assert q['login_hint']==[BODY['username']]
    assert BODY['consumer_secret'] not in r.text
    with a.db() as d:assert BODY['consumer_secret'] not in d.execute('SELECT payload FROM oauth_clients').fetchone()['payload']
    calls=[]
    class Response:
        status_code=200
        def __init__(self,value):self.value=value
        def json(self):return self.value
    class Http:
        def __init__(self,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,data):
            calls.append(data)
            return Response(dict(access_token='token',refresh_token='refresh',instance_url=BODY['org_url']))
        def get(self,*args,**kw):return Response(dict(organization_id='00D000000000001',preferred_username='other@example.com' if wrong_identity else BODY['username']))
    monkeypatch.setattr(a.httpx,'Client',Http)
    r=c.get('/api/orgs/callback',params={'state':q['state'][0],'code':'code'},follow_redirects=False)
    if wrong_identity:
        assert r.status_code==409
        with a.db() as d:assert d.execute('SELECT COUNT(*) FROM orgs').fetchone()[0]==0
        return
    assert r.status_code==303,r.text
    alias=parse_qs(urlsplit(r.headers['location']).query)['org'][0]
    assert load_org_tokens('owner',alias)['oauth_client']['client_secret']==BODY['consumer_secret']
    assert calls[0]['client_secret']==BODY['consumer_secret']
    from Backend.AI.app.services.salesforce_api_client import SalesforceApiClient
    saved=SalesforceApiClient('owner',alias,http=Http())._refresh('token')
    assert saved['oauth_client']['client_id']==BODY['consumer_key']
    assert calls[-1]['grant_type']=='refresh_token'
    assert calls[-1]['client_secret']==BODY['consumer_secret']
    assert c.get('/api/orgs/callback',params={'state':q['state'][0],'code':'code'},follow_redirects=False).status_code==400
    r=c.post('/api/orgs/connect',json={**BODY,'username':None},headers={'Origin':'https://app.example.com'})
    assert r.status_code==422 and BODY['consumer_secret'] not in r.text
