import json
from unittest.mock import patch
import pytest
from Backend.AI.app.tests.test_workspace_regression import client, main, accounts, package
from Backend.AI.app.services import background_jobs as jobs


def scoped(function, *args, **kwargs):
    a=accounts.current_account.set('u');o=accounts.current_org.set('app_ours')
    try:return function(*args, **kwargs)
    finally:accounts.current_account.reset(a);accounts.current_org.reset(o)


def test_generate_returns_accepted_before_any_ai_call(client, monkeypatch):
    monkeypatch.setenv('APP_BACKGROUND_JOBS','true')
    with patch.object(main,'get_ai_provider') as provider:
        response=client.post('/api/plan',json={'requirement':'Create a test field','target_org':'app_ours','generate_files':True,'job_key':'same-request-12345678'},headers={'Origin':'http://localhost:5173'})
    assert response.status_code==202
    assert response.json()['state']=='queued'
    provider.assert_not_called()
    identifier=response.json()['jobId']
    assert client.get('/api/jobs/'+identifier).json()['state']=='queued'
    with accounts.db() as connection:
        assert connection.execute('SELECT COUNT(*) FROM plans').fetchone()[0]==1


def test_idempotent_key_and_owner_scope(client):
    request={'request':{'requirement':'Create X','target_org':'app_ours','generate_files':True}}
    first=scoped(jobs.enqueue,'generate',request,key='key')
    assert scoped(jobs.enqueue,'generate',request,key='key')['jobId']==first['jobId']
    with pytest.raises(main.HTTPException):scoped(jobs.enqueue,'generate',{'request':{'requirement':'Different'}},key='key')
    with pytest.raises(main.HTTPException) as failure:jobs.get_owned(first['jobId'],'another-owner')
    assert failure.value.status_code==404


def test_unowned_conversation_never_queues(client):
    with pytest.raises(main.HTTPException):scoped(jobs.enqueue,'generate',{'conversation_id':'another-chat','request':{}},key='key')
    with accounts.db() as connection:assert connection.execute('SELECT COUNT(*) FROM background_jobs').fetchone()[0]==0


def test_worker_generates_once_and_saves_owned_plan(client):
    tracked=scoped(jobs.enqueue,'generate',{'request':{'requirement':'Create new field','target_org':'app_ours','generate_files':True}},key='key')
    def generate(request):
        plan,bundle=package('PLAN-new','generated');main.plan_store.save(plan);main.metadata_spec_store.save_package(bundle)
        return bundle
    with patch.object(main,'generate_plan',side_effect=generate) as call:
        jobs.process_jobs();jobs.process_jobs()
    call.assert_called_once()
    result=jobs.get_owned(tracked['jobId'],'u')
    assert result['state']=='succeeded' and result['result']['planId']=='PLAN-new'
    assert client.get('/api/plans/PLAN-new').status_code==200


def test_worker_preserves_clarification_and_writes_one_durable_chat_reply(client):
    with accounts.db() as connection:connection.execute('INSERT INTO workspace_conversations VALUES(?,?,?,?,?)',('chat','u','app_ours','Test',0))
    tracked=scoped(jobs.enqueue,'generate',{'request':{'requirement':'Create Account','target_org':'app_ours','generate_files':True},'conversation_id':'chat'},key='key')
    detail={'code':'CLARIFICATION_REQUIRED','question':'Account exists. Reuse it?','message':'Account exists'}
    with patch.object(main,'generate_plan',side_effect=main.HTTPException(422,detail)):
        jobs.process_jobs();jobs.process_jobs()
    result=jobs.get_owned(tracked['jobId'],'u')
    assert result['state']=='failed' and result['result']['detail']==detail
    with accounts.db() as connection:
        messages=connection.execute('SELECT * FROM workspace_messages WHERE conversation_id=?',('chat',)).fetchall()
    assert len(messages)==1 and messages[0]['kind']=='clarification'
    assert messages[0]['content']=='Account exists. Reuse it?'


def approved_package(state):
    plan,bundle=package(state=state)
    plan.status='APPROVED'
    for item in plan.items:item.approval='APPROVED'
    main.plan_store.save(plan)
    bundle.update(approvedHash=bundle['sourceHash'],validatedHash=bundle['sourceHash'] if state=='validated' else None,error=None)
    scoped(main.metadata_spec_store.save_package,bundle)
    return bundle


@pytest.mark.parametrize('kind,state,dry_run',[('validate','generated',True),('deploy','validated',False)])
def test_submission_queues_then_runs_once_with_exact_source(client,monkeypatch,kind,state,dry_run):
    bundle=approved_package(state)
    monkeypatch.setenv('APP_BACKGROUND_JOBS','true')
    response={'result':{'id':'job-id','done':False,'status':'Pending','checkOnly':dry_run}}
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'deploy',return_value=response) as deploy:
        queued=scoped(main.run_default_package,'PLAN-old',dry_run)
        assert queued['state']=='queued'
        deploy.assert_not_called()
        assert client.get('/api/plans/PLAN-old/status').json()['state']=='queued'
        jobs.process_jobs();jobs.process_jobs()
    deploy.assert_called_once()
    assert deploy.call_args.kwargs['dry_run']==dry_run
    assert deploy.call_args.args[0]['sourceHash']==bundle['sourceHash']
    assert main.metadata_spec_store.get_package('PLAN-old')['state']=='pending'


def test_unapproved_and_unvalidated_packages_cannot_queue(client,monkeypatch):
    monkeypatch.setenv('APP_BACKGROUND_JOBS','true')
    with pytest.raises(main.HTTPException):scoped(main.run_default_package,'PLAN-old',False)
    approved_package('generated')
    with pytest.raises(main.HTTPException):scoped(main.run_default_package,'PLAN-old',False)
    with accounts.db() as connection:assert connection.execute('SELECT COUNT(*) FROM background_jobs').fetchone()[0]==0


def test_interrupted_generation_is_not_billed_again_automatically(client):
    tracked=scoped(jobs.enqueue,'generate',{'request':{'requirement':'Create X','target_org':'app_ours','generate_files':True}},key='key')
    with accounts.db() as connection:connection.execute("UPDATE background_jobs SET state='running' WHERE id=?",(tracked['jobId'],))
    with patch.object(main,'generate_plan') as generate:jobs.process_jobs()
    generate.assert_not_called()
    assert jobs.get_owned(tracked['jobId'],'u')['state']=='failed'


def test_interrupted_submission_does_not_repeat_salesforce_write(client):
    bundle=approved_package('validated')
    tracked=scoped(jobs.enqueue,'deploy',{'plan_id':'PLAN-old','source_hash':bundle['sourceHash']},package=bundle)
    with accounts.db() as connection:connection.execute("UPDATE background_jobs SET state='running' WHERE id=?",(tracked['jobId'],))
    with patch.object(main.default_pipeline,'deploy') as deploy:jobs.process_jobs()
    deploy.assert_not_called()
    assert jobs.get_owned(tracked['jobId'],'u')['state']=='unknown'
    assert main.metadata_spec_store.get_package('PLAN-old')['state']=='unknown'


def test_interrupted_submission_with_saved_salesforce_id_resumes_tracking_only(client):
    bundle=approved_package('validated')
    tracked=scoped(jobs.enqueue,'deploy',{'plan_id':'PLAN-old','source_hash':bundle['sourceHash']},package=bundle)
    package_now=main.metadata_spec_store.get_package('PLAN-old')
    package_now.update(state='pending',jobId='known-sf-job');scoped(main.metadata_spec_store.save_package,package_now)
    with accounts.db() as connection:connection.execute("UPDATE background_jobs SET state='running' WHERE id=?",(tracked['jobId'],))
    with patch.object(main.default_pipeline,'deploy') as deploy:jobs.process_jobs()
    deploy.assert_not_called()
    assert jobs.get_owned(tracked['jobId'],'u')['state']=='succeeded'
    assert main.metadata_spec_store.get_package('PLAN-old')['jobId']=='known-sf-job'


def test_redis_failure_leaves_job_committed(client):
    with patch('Backend.AI.app.services.job_notifications.notify') as notify:
        tracked=scoped(jobs.enqueue,'generate',{'request':{}},key='key')
    notify.assert_called_once()
    assert jobs.get_owned(tracked['jobId'],'u')['state']=='queued'


def test_changed_snapshot_rolls_back_job_insertion(client):
    bundle=approved_package('validated')
    with pytest.raises(main.HTTPException):scoped(jobs.enqueue,'deploy',{'plan_id':'PLAN-old','source_hash':'not-the-approved-hash'},package=bundle)
    with accounts.db() as connection:
        assert connection.execute('SELECT COUNT(*) FROM background_jobs').fetchone()[0]==0
        saved=json.loads(connection.execute('SELECT payload FROM workspace_packages WHERE id=?',('PLAN-old',)).fetchone()[0])
    assert saved['package']['state']=='validated'


def test_disconnected_org_is_not_executed_or_exposed(client):
    tracked=scoped(jobs.enqueue,'generate',{'request':{}},key='key')
    with accounts.db() as connection:connection.execute('DELETE FROM orgs WHERE id=?',('app_ours',))
    with patch.object(main,'generate_plan') as generate:jobs.process_jobs()
    generate.assert_not_called()
    with pytest.raises(main.HTTPException) as failure:jobs.get_owned(tracked['jobId'],'u')
    assert failure.value.status_code==404


def test_unrestorable_running_submission_becomes_unknown_not_stuck_running(client):
    bundle=approved_package('validated')
    tracked=scoped(jobs.enqueue,'deploy',{'plan_id':'PLAN-old','source_hash':bundle['sourceHash']},package=bundle)
    with accounts.db() as connection:connection.execute("UPDATE background_jobs SET state='running' WHERE id=?",(tracked['jobId'],))
    with patch.object(main,'restore_workspace_package',side_effect=main.HTTPException(409,'Invalid saved package')),patch.object(main.default_pipeline,'deploy') as deploy:
        jobs.process_jobs()
    deploy.assert_not_called()
    assert jobs.get_owned(tracked['jobId'],'u')['state']=='unknown'
    assert client.get('/api/plans/PLAN-old/status').json()['state']=='unknown'

def test_parallel_chats_queue_but_duplicate_chat_generation_is_rejected(client):
    with accounts.db() as connection:
        for name in ('chat-a', 'chat-b'):
            connection.execute('INSERT INTO workspace_conversations VALUES(?,?,?,?,?)',(name,'u','app_ours',name,0))
    first=scoped(jobs.enqueue,'generate',{'conversation_id':'chat-a','request':{}},key='a')
    other=scoped(jobs.enqueue,'generate',{'conversation_id':'chat-b','request':{}},key='b')
    assert first['jobId'] != other['jobId']
    assert scoped(jobs.enqueue,'generate',{'conversation_id':'chat-a','request':{}},key='a')['jobId']==first['jobId']
    with pytest.raises(main.HTTPException) as exc:
        scoped(jobs.enqueue,'generate',{'conversation_id':'chat-a','request':{}},key='another-key')
    assert exc.value.status_code==409
    with accounts.db() as connection:
        connection.execute("UPDATE background_jobs SET state='succeeded' WHERE id=?",(first['jobId'],))
    next_job=scoped(jobs.enqueue,'generate',{'conversation_id':'chat-a','request':{}},key='next-key')
    assert next_job['jobId'] != first['jobId']
