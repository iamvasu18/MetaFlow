"""Stage 1 security, recovery, races and measurement regressions; no live I/O."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import os
from Backend.AI.app.tests.test_workspace_regression import client, main, accounts, package
from Backend.AI.app.services.metadata_safety import component_path, safe_source_target, source_relative_path
from Backend.AI.app.services.metadata_generator import SalesforceMetadataGenerator
from Backend.AI.app.services.planning_performance import PlanningCache, TimedProvider, timed_generation
from Backend.AI.app.services.evaluation_service import observe_package, record_event, summary, usage_cost


@pytest.mark.parametrize('name',['../Escape__c','Bad/Name__c','C:Drive__c','NUL','CON','Bad\\Name__c','Bad\x00__c'])
def test_names_rejected_before_any_generator_write(tmp_path,name):
    item=SimpleNamespace(metadataType='CustomObject',fullName=name,action='CREATE',config={})
    with pytest.raises(ValueError):SalesforceMetadataGenerator(tmp_path)._generate_item(item)
    assert not (tmp_path/'force-app').exists()


@pytest.mark.parametrize('path',[
    '../outside.xml','force-app/main/default/classes/../outside.cls',
    'force-app/main/default/classes/C:stream.cls', 'force-app/main/default/classes/NUL.cls',
    'force-app/main/default//classes/A.cls','force-app/main/default/classes/A.cls.',
    'force-app/main/default/classes/A\\B.cls','force-app/main/default/classes/A\x00.cls',
])
def test_ambiguous_paths_rejected(path):
    with pytest.raises(ValueError):source_relative_path(path)


def test_symlink_parent_cannot_write_unrelated_source(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()

    parent = tmp_path / "project/force-app/main/default"
    parent.mkdir(parents=True)

    try:
        (parent / "classes").symlink_to(
            outside,
            target_is_directory=True,
        )
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip(
                "Windows symlink permission unavailable; "
                "this guard runs in Linux CI."
            )
        raise

    with pytest.raises(ValueError):
        safe_source_target(
            tmp_path / "project",
            "force-app/main/default/classes/Escape.cls",
        )

    assert not list(outside.iterdir())


def test_base_files_are_guarded_even_with_a_matching_fingerprint():
    _,bundle=package();bundle['baseFiles']={'../escape':'bad'}
    bundle['sourceHash']=main.default_pipeline.fingerprint(bundle)
    with pytest.raises(ValueError):main.default_pipeline.verify_package(bundle)


def test_batch_preflight_does_not_leave_partial_source(tmp_path):
    good=SimpleNamespace(metadataType='CustomObject',fullName='Good__c',action='CREATE',config={})
    bad=SimpleNamespace(metadataType='CustomObject',fullName='../Escape',action='CREATE',config={})
    with pytest.raises(ValueError):SalesforceMetadataGenerator(tmp_path).generate(SimpleNamespace(status='APPROVED',items=[good,bad]))
    assert not (tmp_path/'force-app').exists()


def test_deploy_invalidation_precedes_test_report_rejection(client):
    _,bundle=package();payload={'result':{'id':'job','done':True,'success':True,'checkOnly':False}}
    with patch('Backend.AI.app.services.planning_performance.invalidate_org_context') as invalidate,patch.object(main.default_pipeline,'check_tests',side_effect=ValueError('Missing coverage')):
        main.save_default_result('PLAN-old',bundle,payload,'deploy')
    invalidate.assert_called_once()
    assert main.metadata_spec_store.get_package('PLAN-old')['state']=='unknown'


def test_inflight_discovery_cannot_refill_invalidated_cache():
    cache=PlanningCache();key=('owner','org','scope')
    _,epoch=cache.get(key);cache.invalidate('owner','org');cache.put(key,{'stale':True},epoch)
    assert cache.get(key)[0] is None
    _,fresh=cache.get(key);cache.put(key,{'fresh':True},fresh)
    detached,_=cache.get(key);detached['fresh']=False
    assert cache.get(key)[0]['fresh'] is True


def scoped_save(bundle):
    owner=accounts.current_account.set('u');org=accounts.current_org.set('app_ours')
    try:main.metadata_spec_store.save_package(bundle)
    finally:accounts.current_account.reset(owner);accounts.current_org.reset(org)


def test_interrupted_running_recovers_without_resubmission(client):
    from Backend.AI.app.services.saved_job_monitor import poll_saved_jobs
    _,bundle=package(state='running');bundle['operation']='deploy';scoped_save(bundle)
    with patch.object(main.default_pipeline,'deploy') as deploy,patch.object(main.default_pipeline,'report') as report:
        poll_saved_jobs()
    deploy.assert_not_called();report.assert_not_called()
    recovered=main.metadata_spec_store.get_package('PLAN-old')
    assert recovered['state']=='unknown' and recovered['validatedHash'] is None


def test_monitor_skips_active_plan_but_not_other_plan_locks(client):
    from Backend.AI.app.services.saved_job_monitor import poll_saved_jobs
    _,bundle=package(state='running');bundle['operation']='deploy';scoped_save(bundle)
    entered=Event();release=Event()
    def worker():
        with main.layout_workflow.plan_lock('PLAN-old'):
            entered.set();release.wait(3)
    thread=Thread(target=worker);thread.start();assert entered.wait(1)
    try:
        poll_saved_jobs()
        assert main.metadata_spec_store.get_package('PLAN-old')['state']=='running'
        with main.layout_workflow.try_plan_lock('another-plan') as acquired:assert acquired
        # Already loaded status reads remain fast during submission.
        main.restore_workspace_package('PLAN-old','u','app_ours')
    finally:release.set();thread.join(2)
    assert not thread.is_alive()


def test_legacy_update_quarantined(client,monkeypatch):
    monkeypatch.delenv('APP_ENABLE_LEGACY_WORKFLOW',raising=False)
    with patch.object(main.change_spec_store,'get') as lookup:
        for endpoint in ('generate-change','deploy-change'):
            assert client.post('/api/plans/PLAN-old/'+endpoint).status_code==409
    lookup.assert_not_called()


def test_usage_requires_explicit_model_rates(monkeypatch):
    records=[{'model':'test-model','input_tokens':100,'output_tokens':20}]
    monkeypatch.delenv('AI_PRICING_JSON',raising=False);assert usage_cost(records) is None
    monkeypatch.setenv('AI_PRICING_JSON',json.dumps({'test-model':{'input_tokens':1,'output_tokens':5}}))
    assert usage_cost(records)==0.0002
    assert usage_cost([None]) is None and usage_cost([]) is None
    assert usage_cost([{**records[0],'cache_read_input_tokens':10}]) is None


def test_failed_generation_records_time_and_actual_usage(client):
    class Provider:
        def __init__(self):self.usage_events=[];self.generation_attempts=0
        def generate(self,*args,**kwargs):
            self.generation_attempts+=1
            self.usage_events.append({'model':'test-model','input_tokens':100,'output_tokens':20})
            raise RuntimeError('truncated')
    class Pipeline:
        @timed_generation
        def generate(self,request,provider):return provider.generate('s','u')
    owner=accounts.current_account.set('u');org=accounts.current_org.set('app_ours')
    try:
        with pytest.raises(RuntimeError):Pipeline().generate(None,Provider())
        result=summary('u','app_ours')
    finally:accounts.current_account.reset(owner);accounts.current_org.reset(org)
    assert result['generationAttempts']==1 and result['generatedPlans']==0
    assert result['meanSecondsPerGenerationAttempt'] is not None


def test_metrics_pin_original_source_and_first_validation(client):
    owner=accounts.current_account.set('u');org=accounts.current_org.set('app_ours')
    try:
        _,bundle=package();bundle.update(layoutReady=False,performance={'generationId':'g'})
        observe_package(bundle)
        assert summary('u','app_ours')['generatedPlans']==0
        bundle['layoutReady']=True;observe_package(bundle);observe_package(bundle)
        bundle['sourceHash']='changed';bundle['approvedHash']='changed';observe_package(bundle)
        bundle.update(operation='validate',operationStartedAt=1,state='running');observe_package(bundle)
        assert summary('u','app_ours')['pendingFirstValidations']==1
        bundle['state']='failed';observe_package(bundle);observe_package(bundle)
        bundle.update(operationStartedAt=2,state='validated');observe_package(bundle)
        result=summary('u','app_ours')
        assert result['acceptanceWithoutEdits']=={'numerator':0,'denominator':1,'rate':0}
        assert result['firstTryValidation']=={'numerator':0,'denominator':1,'rate':0}
        assert summary('foreign')['generatedPlans']==0
    finally:accounts.current_account.reset(owner);accounts.current_org.reset(org)


def test_evaluation_endpoint_is_authenticated_and_org_scoped(client):
    assert client.get('/api/evaluation/summary?org_id=foreign').status_code==404
    assert client.get('/api/evaluation/summary?org_id=app_ours').status_code==200
    client.cookies.clear();assert client.get('/api/evaluation/summary').status_code==401


def test_versioned_evaluation_replay():
    from evaluations.run import run_case
    corpus=json.loads((Path(__file__).resolve().parents[4]/'evaluations/stage1-v1.json').read_text())
    results=[run_case(c,corpus['context']) for c in corpus['cases']]
    assert all(r['passed'] for r in results),[r for r in results if not r['passed']]


def test_overview_inflight_read_cannot_refill_after_deploy(client):
    from Backend.AI.app.services.planning_performance import invalidate_org_context
    def collect(*args):
        invalidate_org_context('u','app_ours')
        return {'syncedAt':accounts.time.time(),'organization':{'id':'00D000000000001AAA','name':'Org'},'metrics':{'limits':{}}}
    with patch('Backend.AI.app.services.org_intelligence_service.collect_intelligence',side_effect=collect):
        response=client.get('/api/orgs/app_ours/intelligence')
    assert response.status_code==200,response.text
    with accounts.db() as c:
        assert c.execute('SELECT payload FROM org_intelligence_cache WHERE org_id=?',('app_ours',)).fetchone() is None
        assert c.execute('SELECT epoch FROM org_cache_epochs WHERE user_id=? AND org_id=?',('u','app_ours')).fetchone()['epoch']==1


def test_concurrent_submission_is_serialized_and_second_is_blocked(client):
    from fastapi import HTTPException
    plan=main.plan_store.get('PLAN-old');plan.status='APPROVED'
    for item in plan.items:item.approval='APPROVED'
    bundle=main.metadata_spec_store.get_package('PLAN-old');bundle['state']='generated';scoped_save(bundle)
    entered=Event();release=Event();second_started=Event();results=[]
    def submit(*args,**kwargs):
        entered.set();assert release.wait(3)
        return {'result':{'id':'job','done':False,'status':'Pending'}}
    def worker(second=False):
        owner=accounts.current_account.set('u');org=accounts.current_org.set('app_ours')
        try:
            if second:second_started.set()
            try:results.append(main.run_default_package('PLAN-old',dry_run=True)['state'])
            except HTTPException as error:results.append(error.status_code)
        finally:accounts.current_account.reset(owner);accounts.current_org.reset(org)
    with patch.object(main.default_pipeline,'verify_package'),patch.object(main.default_pipeline,'assert_plan'),patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'check_tests'),patch.object(main.default_pipeline,'deploy',side_effect=submit) as deploy:
        first=Thread(target=worker);second=Thread(target=worker,args=(True,))
        first.start();assert entered.wait(1);second.start();assert second_started.wait(1)
        release.set();first.join(3);second.join(3)
        assert not first.is_alive() and not second.is_alive()
        assert results==['pending',409] and deploy.call_count==1


def test_acceptance_and_cost_include_repairs_without_resetting_baseline(client,monkeypatch):
    owner=accounts.current_account.set('u');org=accounts.current_org.set('app_ours')
    try:
        _,bundle=package();bundle['performance']={'generationId':'initial'};bundle['layoutReady']=True
        observe_package(bundle)
        record_event('generation',{'generationId':'initial','totalSeconds':10,'costUsd':0.1},'PLAN-old','initial')
        record_event('generation',{'generationId':'repair','totalSeconds':3,'costUsd':0.05},'PLAN-old','repair')
        bundle['approvedHash']=bundle['sourceHash'];observe_package(bundle)
        result=summary('u','app_ours')
        assert result['acceptanceWithoutEdits']['rate']==1
        assert result['meanSecondsPerSavedPlan']==13
        assert result['meanKnownCostUsdPerSavedPlan']==pytest.approx(0.15)
        selected=deepcopy(bundle);selected['plan']['id']='PLAN-subset';selected['evaluationOriginPlanId']='PLAN-old'
        observe_package(selected)
        assert summary('u','app_ours')['generatedPlans']==1
    finally:accounts.current_account.reset(owner);accounts.current_org.reset(org)


def test_anthropic_usage_is_kept_when_output_is_truncated(monkeypatch):
    from Backend.AI.app.providers.ai_provider import AnthropicProvider
    monkeypatch.setenv('ANTHROPIC_MAX_TOKENS','4096')
    monkeypatch.setenv('ANTHROPIC_MAX_INPUT_TOKENS','180000')
    with patch('Backend.AI.app.providers.ai_provider.anthropic.Anthropic') as factory:
        client=factory.return_value
        client.messages.count_tokens.return_value=SimpleNamespace(input_tokens=100)
        client.messages.create.return_value=SimpleNamespace(model='test-model',stop_reason='max_tokens',usage=SimpleNamespace(input_tokens=100,output_tokens=20),content=[])
        provider=AnthropicProvider(api_key='fixture-key',model='test-model')
        timed=TimedProvider(provider)
        with pytest.raises(RuntimeError):timed.generate('system','user')
    assert timed.usage==[{'model':'test-model','input_tokens':100,'output_tokens':20,'cache_creation_input_tokens':0,'cache_read_input_tokens':0}]
    assert len(timed.prompt_hashes)==1


def test_transport_failure_never_reuses_previous_usage(monkeypatch):
    class Provider:
        def __init__(self):self.usage_events=[];self.generation_attempts=0
        def generate(self,*args,**kwargs):
            self.generation_attempts+=1
            if self.generation_attempts==1:
                self.usage_events.append({'model':'test-model','input_tokens':100,'output_tokens':20})
                return '{}'
            raise RuntimeError('network outcome unknown')
    measured=TimedProvider(Provider());measured.generate('system','user')
    with pytest.raises(RuntimeError):measured.generate('system','user')
    assert len(measured.usage)==2 and measured.usage[1] is None
    monkeypatch.setenv('AI_PRICING_JSON','{"test-model":{"input_tokens":1,"output_tokens":5}}')
    assert usage_cost(measured.usage) is None



def test_legacy_create_paths_cannot_bypass_package_review(client,monkeypatch):
    monkeypatch.delenv('APP_ENABLE_LEGACY_WORKFLOW',raising=False)
    with patch.object(main,'get_ai_provider') as provider:
        response=client.post('/api/plan',json={'requirement':'Create an object','target_org':'app_ours','generate_files':False})
        assert response.status_code==409
    provider.assert_not_called()
    main.metadata_spec_store._packages.pop('PLAN-old',None)
    # Remove its snapshot so account middleware cannot restore a reviewed package.
    with accounts.db() as c:c.execute('DELETE FROM workspace_packages WHERE id=?',('PLAN-old',))
    with patch.object(main.SalesforceDeploymentExecutor,'deploy') as deploy:
        for endpoint in ('generate-metadata','execute','deploy'):
            assert client.post('/api/plans/PLAN-old/'+endpoint).status_code==409
    deploy.assert_not_called()
