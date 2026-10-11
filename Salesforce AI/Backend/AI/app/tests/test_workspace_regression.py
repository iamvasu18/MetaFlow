import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


accounts=importlib.import_module('Backend.AI.app.account_api')
main=importlib.import_module('Backend.AI.app.main')
integration=importlib.import_module('Backend.AI.app.services.integration_service')
revision=importlib.import_module('Backend.AI.app.services.plan_revision_service')
Plan=importlib.import_module('Backend.AI.app.validators.plan_validator').ImplementationPlan


def package(plan_id='PLAN-old',state='failed'):
    plan=Plan.model_validate({'id':plan_id,'requirementId':'req','summary':'Create description field','items':[{'id':'item','action':'CREATE','metadataType':'CustomField','fullName':'Metaflow__c.UI_Description__c','config':{},'approval':'PENDING'}]})
    source={'force-app/main/default/objects/Metaflow__c/fields/UI_Description__c.field-meta.xml':'<CustomField />'}
    result={'id':plan_id,'plan':plan.model_dump(),'requirement':'Create a UI description field on Metaflow','files':source,'baseFiles':source,'targetOrg':'app_ours','apiVersion':'65.0','components':[{'metadataType':'CustomField','fullName':'Metaflow__c.UI_Description__c'}],'testClasses':[],'metadataSpecification':None,'layoutSelections':{},'layoutReady':True,'state':state,'error':'Salesforce reported invalid field length','componentName':plan.summary}
    result['sourceHash']=main.default_pipeline.fingerprint(result)
    return plan,result

@pytest.fixture
def client(tmp_path):
    accounts.DB=tmp_path/'accounts.sqlite3'
    os.environ['APP_PUBLIC_URL']='http://localhost:5173'
    with accounts.db() as db:
        db.execute('INSERT INTO users VALUES(?,?,?,?,?)',('u','u@test','User','salt','hash'))
        db.execute('INSERT INTO sessions VALUES(?,?,?)',(accounts.digest('session'),'u',accounts.time.time()+1000))
        db.execute('INSERT INTO orgs VALUES(?,?,?,?,?,?)',('app_ours','u','Org','Sandbox','user@org','https://example.salesforce.com'))
        db.execute('INSERT INTO plans VALUES(?,?,?)',('PLAN-old','u','app_ours'))
    plan,bundle=package()
    main.plan_store.save(plan)
    token=accounts.current_account.set('u');org=accounts.current_org.set('app_ours')
    try:main.metadata_spec_store.save_package(bundle)
    finally:accounts.current_account.reset(token);accounts.current_org.reset(org)
    options={'ready':False,'objects':[],'selections':[],'snapshotId':'snapshot'}
    with patch.object(main.layout_workflow,'options',return_value=options),TestClient(main.app) as c:
        c.cookies.set('app_session','session');yield c


def test_revision_is_new_draft_and_owned(client):
    _,generated=package('PLAN-new','generated');generated.pop('error')
    with patch.object(main.default_pipeline,'generate',return_value=generated),patch.object(main,'get_ai_provider',return_value=object()):
        response=client.post('/api/plans/PLAN-old/revise',json={'requirement':'Create a longer description field'})
    assert response.status_code==200,response.text
    assert response.json()['plan']['status']=='DRAFT' and not response.json().get('approvedHash')
    with accounts.db() as db:
        assert db.execute('SELECT user_id FROM plans WHERE id=?',('PLAN-new',)).fetchone()[0]=='u'
        assert db.execute('SELECT id FROM workspace_chats WHERE id=?',('PLAN-new',)).fetchone()


def test_repair_uses_saved_failure_and_exact_original_requirement(client):
    _,generated=package('PLAN-old','generated');generated.pop('error')
    with patch.object(main.default_pipeline,'generate',return_value=generated) as generate,patch.object(main,'get_ai_provider',return_value=object()):
        response=client.post('/api/plans/PLAN-old/repair',json={'component_name':'Metaflow__c.UI_Description__c'})
    assert response.status_code==200,response.text
    request,provider=generate.call_args.args
    assert request.requirement=='Create a UI description field on Metaflow'
    assert isinstance(provider,revision.RepairProvider)
    assert 'invalid field length' in provider.context['failureEvidence']
    assert provider.context['focusComponent']=='Metaflow__c.UI_Description__c'
    assert not response.json().get('approvedHash')

@pytest.mark.parametrize('state',['running','pending','unknown','deployed'])
def test_repair_blocks_uncertain_and_completed_operations(client,state):
    plan,bundle=package(state=state);main.metadata_spec_store.save_package(bundle)
    with patch.object(main,'get_ai_provider') as provider:
        assert client.post('/api/plans/PLAN-old/repair',json={}).status_code==409
        provider.assert_not_called()


def test_saved_package_survives_memory_reset(client):
    main.plan_store._plans.pop('PLAN-old',None)
    main.metadata_spec_store._packages.pop('PLAN-old',None)
    response=client.get('/api/plans/PLAN-old')
    assert response.status_code==200,response.text
    assert response.json()['requirement']=='Create a UI description field on Metaflow'
    assert response.json()['state']=='failed'


def test_foreign_plan_blocked(client):
    with accounts.db() as db:db.execute('INSERT INTO plans VALUES(?,?,?)',('PLAN-other','other','app_ours'))
    with patch.object(main,'get_ai_provider') as provider:
        assert client.post('/api/plans/PLAN-other/repair',json={}).status_code==404
        provider.assert_not_called()


def test_secrets_are_encrypted_and_account_scoped(client):
    settings={'provider':'anthropic','api_key':'private-secret-key','model':'model','source':'account'}
    integration.save_settings('u','ai',settings)
    with accounts.db() as db:payload=db.execute('SELECT payload FROM integrations WHERE user_id=?',('u',)).fetchone()[0]
    assert 'private-secret-key' not in payload
    assert integration.load_settings('u','ai')['api_key']=='private-secret-key'
    assert integration.load_settings('other','ai') is None
    response=client.get('/api/integrations')
    assert response.status_code==200 and 'private-secret-key' not in response.text


def test_ai_verification_and_model_routing(client):
    fake=SimpleNamespace(models=SimpleNamespace(list=lambda:[SimpleNamespace(id='available-model')]))
    with patch('anthropic.Anthropic',return_value=fake):
        response=client.post('/api/integrations/ai',json={'model':'available-model','api_key':'private-key'})
    assert response.status_code==200 and 'private-key' not in response.text
    factory=importlib.import_module('Backend.AI.app.providers.provider_factory')
    context=accounts.current_account.set('u')
    try:
        with patch.object(factory,'AnthropicProvider',return_value='provider') as provider:
            assert factory.get_ai_provider()=='provider'
            provider.assert_called_once_with(api_key='private-key',model='available-model')
    finally:accounts.current_account.reset(context)


def test_bad_model_does_not_replace_settings(client):
    fake=SimpleNamespace(models=SimpleNamespace(list=lambda:[SimpleNamespace(id='available-model')]))
    with patch('anthropic.Anthropic',return_value=fake):
        assert client.post('/api/integrations/ai',json={'model':'bad-model','api_key':'private-key'}).status_code==422
    assert integration.load_settings('u','ai') is None


def test_jira_site_is_validated_before_sending_credentials(client):
    with patch.object(integration,'jira_get') as request:
        response=client.post('/api/integrations/jira',json={'site':'http://127.0.0.1','email':'u@test','api_token':'secret'})
    assert response.status_code==422;request.assert_not_called()


def test_jira_verified_then_stories_are_read(client):
    with patch.object(integration,'jira_get',return_value={'accountId':'id','displayName':'User'}):
        response=client.post('/api/integrations/jira',json={'site':'https://example.atlassian.net','email':'u@test','api_token':'private-token'})
    assert response.status_code==200 and 'private-token' not in response.text
    payload={'issues':[{'key':'ABC-1','fields':{'summary':'Create field','description':{'content':[{'text':'Description'}]},'status':{'name':'To do'}}}]}
    with patch.object(integration,'jira_get',return_value=payload):
        result=client.get('/api/integrations/jira/stories')
    assert result.status_code==200 and result.json()[0]['description']=='Description'


def test_approved_pending_job_survives_restart_and_cannot_be_repaired(client):
    plan,bundle=package(state='pending')
    plan.status='APPROVED'
    for item in plan.items:item.approval='APPROVED'
    bundle['approvedHash']=bundle['sourceHash'];bundle['jobId']='job-123';bundle['operation']='deploy'
    main.plan_store.save(plan)
    owner=accounts.current_account.set('u');org=accounts.current_org.set('app_ours')
    try:main.metadata_spec_store.save_package(bundle)
    finally:accounts.current_account.reset(owner);accounts.current_org.reset(org)
    main.plan_store._plans.pop('PLAN-old',None);main.metadata_spec_store._packages.pop('PLAN-old',None)
    response=client.get('/api/plans/PLAN-old')
    assert response.status_code==200,response.text
    result=response.json()
    assert result['state']=='pending' and result['jobId']=='job-123'
    assert result['approvedHash']==result['sourceHash'] and result['plan']['status']=='APPROVED'
    assert client.post('/api/plans/PLAN-old/repair',json={}).status_code==409


def test_corrupted_saved_source_is_blocked(client):
    with accounts.db() as db:
        row=db.execute('SELECT payload FROM workspace_packages WHERE id=?',('PLAN-old',)).fetchone()
        snapshot=json.loads(row['payload']);snapshot['package']['files']['force-app/main/default/objects/Metaflow__c/fields/UI_Description__c.field-meta.xml']='tampered'
        db.execute('UPDATE workspace_packages SET payload=? WHERE id=?',(json.dumps(snapshot),'PLAN-old'))
    main.plan_store._plans.pop('PLAN-old',None);main.metadata_spec_store._packages.pop('PLAN-old',None)
    assert client.get('/api/plans/PLAN-old').status_code==409


def test_generation_failure_repair_preserves_original_requirement(client):
    _,generated=package('PLAN-retried','generated');generated.pop('error')
    with patch.object(main.default_pipeline,'generate',return_value=generated) as generate,patch.object(main,'get_ai_provider',return_value=object()):
        result=client.post('/api/plan',json={'requirement':'Create a UI description field on Metaflow','target_org':'app_ours','generate_files':True,'repair_error':'Invalid generated metadata JSON'})
    assert result.status_code==409,result.text
    generate.assert_not_called()
