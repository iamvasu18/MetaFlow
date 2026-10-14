"""Authenticated plan lifecycle tests for the current saved-source workflow."""
from unittest.mock import patch
from Backend.AI.app.tests.test_workspace_regression import client,main,package
from Backend.AI.app.tests.test_background_jobs import scoped


def reviewed(state='validated'):
    plan,bundle=package(state=state)
    bundle.update(error=None,approvedHash=None,validatedHash=bundle['sourceHash'] if state=='validated' else None)
    main.plan_store.save(plan)
    scoped(main.metadata_spec_store.save_package,bundle)
    return plan,bundle


def test_approve_plan_endpoint(client):
    plan,bundle=reviewed()
    with patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'deploy') as submit:
        response=client.post(f'/api/plans/{plan.id}/approve',json={'source_hash':bundle['sourceHash']})
    assert response.status_code==200,response.text
    assert response.json()['approvedHash']==bundle['sourceHash']
    assert main.plan_store.get(plan.id).status=='APPROVED'
    submit.assert_not_called()


def test_reject_plan_endpoint(client):
    plan,bundle=reviewed('generated')
    response=client.post(f'/api/plans/{plan.id}/reject')
    assert response.status_code==200,response.text
    assert main.plan_store.get(plan.id).status=='REJECTED'
    assert not response.json().get('approvedHash')


def test_approved_plan_cannot_be_rejected_through_api(client):
    plan,_=reviewed();plan.status='APPROVED'
    assert client.post(f'/api/plans/{plan.id}/reject').status_code==422


def test_rejected_plan_cannot_be_approved_through_api(client):
    plan,bundle=reviewed();plan.status='REJECTED'
    assert client.post(f'/api/plans/{plan.id}/approve',json={'source_hash':bundle['sourceHash']}).status_code==422


def test_approve_nonexistent_plan(client):
    assert client.post('/api/plans/missing/approve',json={'source_hash':'0'*64}).status_code==404
