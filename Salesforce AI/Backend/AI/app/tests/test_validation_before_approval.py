from unittest.mock import patch
import pytest
from Backend.AI.app.tests.test_workspace_regression import client, main, accounts, package
from Backend.AI.app.tests.test_background_jobs import scoped

def draft():
    plan,bundle=package(state='generated')
    bundle.update(approvedHash=None,validatedHash=None,error=None)
    main.plan_store.save(plan)
    scoped(main.metadata_spec_store.save_package,bundle)
    return plan,bundle

def test_draft_can_validate_without_user_approval_but_cannot_deploy(client):
    plan,bundle=draft()
    payload={'result':{'id':'job-validation','done':True,'success':True,'status':'Succeeded','checkOnly':True}}
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'deploy',return_value=payload) as submit:
        result=scoped(main.run_default_package,plan.id,True)
        assert result['state']=='validated'
        assert result['validatedHash']==bundle['sourceHash']
        assert not result.get('approvedHash')
        assert main.plan_store.get(plan.id).status=='DRAFT'
        with pytest.raises(main.HTTPException): scoped(main.run_default_package,plan.id,False)
        scoped(main.run_default_package,plan.id,True)
        assert submit.call_count==1

def test_approval_requires_validation_of_exact_source_and_submits_nothing(client):
    plan,bundle=draft()
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.layout_workflow,'options',return_value={'ready':True}),patch.object(main.default_pipeline,'deploy') as submit:
        with pytest.raises(main.HTTPException) as failure:
            scoped(main.approve_plan,plan.id,main.DefaultApprovalRequest(source_hash=bundle['sourceHash']))
        assert failure.value.status_code==409
        bundle.update(state='validated',validatedHash=bundle['sourceHash'])
        scoped(main.metadata_spec_store.save_package,bundle)
        result=scoped(main.approve_plan,plan.id,main.DefaultApprovalRequest(source_hash=bundle['sourceHash']))
        assert result['approvedHash']==bundle['sourceHash']
        assert main.plan_store.get(plan.id).status=='APPROVED'
        submit.assert_not_called()

def test_layout_choices_block_validation_submission(client):
    plan,bundle=draft();bundle['layoutReady']=False
    scoped(main.metadata_spec_store.save_package,bundle)
    with patch.object(main.default_pipeline,'deploy') as submit:
        assert scoped(main.validate_generated_draft,plan.id)['state']=='generated'
        submit.assert_not_called()

def test_auto_validation_failure_keeps_draft_and_error(client):
    plan,bundle=draft()
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'deploy',side_effect=ValueError('Compiler failure')):
        result=scoped(main.validate_generated_draft,plan.id)
    assert result['state']=='failed'
    assert 'Compiler failure' in result['error']
    assert not result.get('approvedHash')

def test_real_pipeline_allows_draft_check_only_and_blocks_unapproved_write(client):
    plan,bundle=draft()
    with patch.object(main.default_pipeline,'ensure_new',side_effect=RuntimeError('reached live preflight')) as preflight:
        with pytest.raises(ValueError,match='approve'):
            main.default_pipeline.deploy(bundle,dry_run=False)
        preflight.assert_not_called()
        with pytest.raises(RuntimeError,match='reached live preflight'):
            main.default_pipeline.deploy(bundle,dry_run=True)
        assert preflight.call_count==1

def test_unapproved_validation_can_queue_and_worker_resume(client,monkeypatch):
    plan,bundle=draft()
    monkeypatch.setenv('APP_BACKGROUND_JOBS','true')
    from Backend.AI.app.services import background_jobs as jobs
    response={'result':{'id':'draft-job','done':False,'status':'Pending','checkOnly':True}}
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'deploy',return_value=response) as submit:
        result=scoped(main.validate_generated_draft,plan.id)
        assert result['state']=='queued'
        submit.assert_not_called()
        jobs.process_jobs()
        assert submit.call_count==1
    assert main.metadata_spec_store.get_package(plan.id)['state']=='pending'
    assert not main.metadata_spec_store.get_package(plan.id).get('approvedHash')

def test_generation_starts_validation_without_recording_approval(client):
    plan,bundle=package('PLAN-auto','generated')
    bundle.update(approvedHash=None,validatedHash=None,error=None)
    response={'result':{'id':'auto-job','done':False,'status':'Pending','checkOnly':True}}
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.layout_workflow,'options',return_value={'ready':True}),patch.object(main.default_pipeline,'generate',return_value=bundle),patch.object(main.default_pipeline,'prepare_review',return_value=bundle),patch.object(main.default_pipeline,'deploy',return_value=response) as submit:
        result=scoped(main.build_default_draft,'Create description field','app_ours',object())
    assert submit.call_args.kwargs['dry_run'] is True
    assert result['state']=='pending' and result['operation']=='validate'
    assert not result.get('approvedHash')
    assert main.plan_store.get(plan.id).status=='DRAFT'
