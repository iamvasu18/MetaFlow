import sys
from pathlib import Path
from Backend.AI.app.tests.test_workspace_regression import client, main
from unittest.mock import patch
import pytest


def approve_fixture():
    plan=main.plan_store.get('PLAN-old')
    plan.status='APPROVED'
    for item in plan.items:item.approval='APPROVED'
    bundle=main.metadata_spec_store.get_package('PLAN-old')
    bundle['approvedHash']=bundle['sourceHash']
    bundle['state']='generated'
    bundle['error']=None
    bundle.pop('validatedHash',None)
    main.metadata_spec_store.save_package(bundle)
    return bundle


@pytest.mark.parametrize('state',['generated','failed','validated'])
def test_deploy_requires_prior_exact_validation(client,state):
    bundle=approve_fixture();bundle['state']=state
    main.metadata_spec_store.save_package(bundle)
    with patch.object(main.default_pipeline,'deploy') as deploy:
        response=client.post('/api/plans/PLAN-old/deploy',json={'approved':True,'source_hash':bundle['sourceHash']})
    assert response.status_code==409,response.text
    deploy.assert_not_called()


def test_validate_sets_hash_without_deploying(client):
    bundle=approve_fixture()
    result={'result':{'done':True,'success':True,'id':'validation-job'}}
    with patch.object(main.default_pipeline,'verify_package'),patch.object(main.default_pipeline,'assert_plan'),patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'check_tests'),patch.object(main.default_pipeline,'deploy',return_value=result) as deploy:
        response=client.post('/api/plans/PLAN-old/validate')
    assert response.status_code==200,response.text
    assert response.json()['state']=='validated'
    assert response.json()['validatedHash']==bundle['sourceHash']
    assert deploy.call_count==1 and deploy.call_args.kwargs['dry_run'] is True


def test_validation_failure_never_enables_deploy(client):
    bundle=approve_fixture()
    result={'result':{'done':True,'success':False,'id':'failed-job','details':{'componentFailures':[{'problem':'LWC1503','fileName':'component.js'}]}}}
    with patch.object(main.default_pipeline,'verify_package'),patch.object(main.default_pipeline,'assert_plan'),patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'check_tests'),patch.object(main.default_pipeline,'deploy',return_value=result):
        response=client.post('/api/plans/PLAN-old/validate')
    assert response.json()['state']=='failed' and response.json()['validatedHash'] is None
    assert response.json()['lastResult']['result']['details']['componentFailures'][0]['problem']=='LWC1503'


def test_deploy_requires_validation_then_submits_actual_deploy(client):
    bundle=approve_fixture();bundle['state']='validated';bundle['validatedHash']=bundle['sourceHash']
    main.metadata_spec_store.save_package(bundle)
    result={'result':{'done':True,'success':True,'id':'job'}}
    with patch.object(main.default_pipeline,'verify_package'),patch.object(main.default_pipeline,'assert_plan'),patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'check_tests'),patch.object(main.default_pipeline,'deploy',return_value=result) as deploy:
        response=client.post('/api/plans/PLAN-old/deploy',json={'approved':True,'source_hash':bundle['sourceHash']})
    assert response.status_code==200,response.text
    assert response.json()['state']=='deployed'
    assert [call.kwargs['dry_run'] for call in deploy.call_args_list]==[False]
