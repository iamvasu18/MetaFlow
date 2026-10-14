"""Authenticated deployment gates; old implicit validation-on-deploy is retired."""
from unittest.mock import patch
from Backend.AI.app.tests.test_workspace_regression import client,main,package
from Backend.AI.app.tests.test_background_jobs import scoped


def prepared(approved=True):
    plan,bundle=package(state='validated')
    plan.status='APPROVED' if approved else 'DRAFT'
    for item in plan.items:item.approval='APPROVED' if approved else 'PENDING'
    bundle.update(error=None,approvedHash=bundle['sourceHash'] if approved else None,validatedHash=bundle['sourceHash'])
    main.plan_store.save(plan)
    scoped(main.metadata_spec_store.save_package,bundle)
    return plan,bundle


def deploy(client,plan,bundle):
    return client.post(f'/api/plans/{plan.id}/deploy',json={'source_hash':bundle['sourceHash']})


def test_deploy_endpoint_requires_existing_plan(client):
    assert client.post('/api/plans/missing/deploy',json={'source_hash':'0'*64}).status_code==404


def test_deploy_endpoint_rejects_unapproved_plan(client):
    plan,bundle=prepared(False)
    with patch.object(main.default_pipeline,'deploy') as submit:
        assert deploy(client,plan,bundle).status_code==422
        submit.assert_not_called()


def test_deploy_endpoint_requires_metadata_specification(client):
    # Unified deployment requires the exact reviewed package, not AI metadata alone.
    plan,bundle=prepared()
    with patch.object(main.default_pipeline,'deploy') as submit:
        assert client.post(f'/api/plans/{plan.id}/deploy',json={'source_hash':'0'*64}).status_code==409
        submit.assert_not_called()


def test_deploy_endpoint_success(client):
    plan,bundle=prepared()
    result={'result':{'id':'deploy-job','done':True,'success':True,'checkOnly':False}}
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'deploy',return_value=result) as submit:
        response=deploy(client,plan,bundle)
        assert response.status_code==200,response.text
        assert response.json()['state']=='deployed'
        assert submit.call_args.kwargs['dry_run'] is False
        assert deploy(client,plan,bundle).status_code==409
        assert submit.call_count==1


def test_deploy_endpoint_handles_deployment_failure(client):
    plan,bundle=prepared()
    result={'result':{'id':'failed-job','done':True,'success':False,'checkOnly':False,'details':{'componentFailures':[{'fullName':'Metaflow__c.UI_Description__c','problem':'Invalid field'}]}}}
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'deploy',return_value=result):
        response=deploy(client,plan,bundle)
    assert response.status_code==200,response.text
    assert response.json()['state']=='failed'
    assert response.json()['lastResult']==result


def test_deploy_endpoint_rejects_invalid_metadata(client):
    plan,bundle=prepared()
    bundle['files']=dict(bundle['files'])
    bundle['files'][next(iter(bundle['files']))]='<CustomField><label>Changed</label></CustomField>'
    scoped(main.metadata_spec_store.save_package,bundle)
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'deploy') as submit:
        assert deploy(client,plan,bundle).status_code==422
        submit.assert_not_called()
