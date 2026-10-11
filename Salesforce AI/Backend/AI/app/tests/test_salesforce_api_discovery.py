import importlib
import httpx
import pytest
from fastapi import HTTPException
from cryptography.fernet import Fernet
from Backend.AI.app.services.salesforce_api_client import (
    SalesforceApiClient, instance_url, save_org_tokens, load_org_tokens,
)

accounts=importlib.import_module('Backend.AI.app.account_api')

@pytest.fixture
def connection(tmp_path,monkeypatch):
    monkeypatch.setattr(accounts,'DB',tmp_path/'accounts.sqlite3')
    monkeypatch.setenv('APP_ENCRYPTION_KEY',Fernet.generate_key().decode())
    monkeypatch.setenv('SF_OAUTH_CLIENT_ID','test-client')
    with accounts.db() as db:
        db.execute('INSERT INTO users VALUES(?,?,?,?,?)',('u','u@test','User','salt','hash'))
        db.execute('INSERT INTO orgs VALUES(?,?,?,?,?,?)',('org','u','Org','Sandbox','u@org','https://example.salesforce.com'))
    tokens={'access_token':'secret-access','refresh_token':'secret-refresh','instance_url':'https://example.salesforce.com'}
    save_org_tokens('u','org',tokens,'https://test.salesforce.com')
    def client(handler):
        return SalesforceApiClient('u','org',http=httpx.Client(transport=httpx.MockTransport(handler)))
    return client

def test_encrypted_and_owned(connection):
    with accounts.db() as db:
        payload=db.execute('SELECT payload FROM org_tokens').fetchone()[0]
    assert 'secret-access' not in payload and 'secret-refresh' not in payload
    assert load_org_tokens('u','org')['access_token']=='secret-access'
    with pytest.raises(HTTPException) as error:load_org_tokens('other-user','org')
    assert error.value.status_code==404

def test_missing_tokens_requires_reconnect(connection):
    with accounts.db() as db:db.execute('DELETE FROM org_tokens')
    with pytest.raises(HTTPException) as error:load_org_tokens('u','org')
    assert error.value.status_code==409

@pytest.mark.parametrize('url',['http://example.salesforce.com','https://evil.com','https://example.salesforce.com.evil.com','https://u:p@example.salesforce.com','https://example.salesforce.com/path','https://example.salesforce.com:bad','https://[bad'])
def test_instance_guard(url):
    with pytest.raises(HTTPException):instance_url(url)

def test_refresh_rotation_and_retry(connection):
    seen=[]
    def handler(request):
        seen.append(request)
        if request.method=='POST':
            assert request.url.host=='test.salesforce.com'
            return httpx.Response(200,json={'access_token':'new-access','refresh_token':'new-refresh'})
        if request.headers['Authorization']=='Bearer secret-access':return httpx.Response(401)
        assert request.headers['Authorization']=='Bearer new-access'
        return httpx.Response(200,json={'records':[],'done':True})
    assert connection(handler).query('SELECT Id FROM Organization')['records']==[]
    assert len(seen)==3
    assert load_org_tokens('u','org')['refresh_token']=='new-refresh'

def test_paginated_query(connection):
    def handler(request):
        if request.url.path.endswith('/query'):
            return httpx.Response(200,json={'records':[{'Id':'first'}],'done':False,'nextRecordsUrl':'/services/data/v67.0/query/cursor-1'})
        return httpx.Response(200,json={'records':[{'Id':'second'}],'done':True})
    assert len(connection(handler).query('SELECT Id FROM Organization')['records'])==2

@pytest.mark.parametrize('payload',[{'records':[]},{'records':[],'done':False,'nextRecordsUrl':'https://evil.com'},{'records':[],'done':False,'nextRecordsUrl':'/services/data/v67.0/query/../../limits'}])
def test_incomplete_or_unsafe_inventory(connection,payload):
    client=connection(lambda request:httpx.Response(200,json=payload))
    with pytest.raises((HTTPException,ValueError)):client.query('SELECT Id FROM Organization')

def test_error_body_is_not_exposed(connection):
    client=connection(lambda request:httpx.Response(400,json=[{'errorCode':'INVALID_FIELD','message':'secret-access'}]))
    with pytest.raises(HTTPException) as error:client.list_objects()
    assert 'INVALID_FIELD' in error.value.detail and 'secret-access' not in error.value.detail

def test_namespaced_components(connection):
    client=connection(lambda request:httpx.Response(200,json={'records':[{'DeveloperName':'Search','NamespacePrefix':'vendor'}],'done':True}))
    assert client.list_components('LightningComponentBundle')==[{'fullName':'vendor__Search'}]

def test_describe_preserves_full_fields(connection):
    field={'name':'Days__c','type':'double','calculated':False,'createable':True,'scale':2}
    client=connection(lambda request:httpx.Response(200,json={'name':'Leave__c','fields':[field]}))
    assert client.describe_object('Leave__c')['fields']==[field]
    with pytest.raises(ValueError):client.describe_object('../Account')

def test_rule_metadata_read_is_scoped_to_one_id(connection):
    ident='03d000000000001AAA'
    def handler(request):
        query=request.url.params['q']
        if 'Metadata' in query:
            assert "WHERE Id = '"+ident+"'" in query
            rows=[{'Id':ident,'Metadata':{'active':True,'errorConditionFormula':'Amount__c < 0','errorMessage':'Invalid amount'}}]
        else:
            assert "EntityDefinition.QualifiedApiName = 'Order__c'" in query
            rows=[{'Id':ident,'ValidationName':'CheckAmount'}]
        return httpx.Response(200,json={'records':rows,'done':True})
    context=connection(handler).enrich_validation_rules({'objects':[{'name':'Order__c','fields':[]}]})
    assert context['objects'][0]['validationRules'][0]['fullName']=='Order__c.CheckAmount'
    assert context['validationRuleDiscovery']['status']=='complete'

def test_owned_metadata_service_uses_api_not_cli(connection,monkeypatch):
    from Backend.AI.app.salesforce.metadata_service import SalesforceMetadataService
    token=accounts.current_account.set('u')
    try:service=SalesforceMetadataService('org')
    finally:accounts.current_account.reset(token)
    assert isinstance(service.api,SalesforceApiClient)
    service.api=connection(lambda request:httpx.Response(200,json={'sobjects':[{'name':'Account','label':'Account'}]}))
    def fail_cli(*args):raise AssertionError('Owned discovery must not spawn Salesforce CLI')
    monkeypatch.setattr(service,'_run_sf_command',fail_cli)
    assert service.list_objects()==[{'name':'Account','fullName':'Account','label':'Account'}]
