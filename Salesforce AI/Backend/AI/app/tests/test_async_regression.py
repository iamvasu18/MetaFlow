import sys
from pathlib import Path
from Backend.AI.app.tests.test_workspace_regression import client, main, package
from unittest.mock import patch


def test_cli_async_submission_and_pending_id(tmp_path):
    import json
    from Backend.AI.app.services.metadata_service import DefaultMetadataPipeline
    plan,bundle=package(state='generated')
    plan.status='APPROVED'
    for item in plan.items:item.approval='APPROVED'
    bundle['plan']=plan.model_dump();bundle['approvedHash']=bundle['sourceHash'];bundle['metadataSpecification']=None
    (tmp_path/'sfdx-project.json').write_text(json.dumps({'sourceApiVersion':'66.0','packageDirectories':[{'path':'force-app'}]}))
    pipeline=DefaultMetadataPipeline(project_root=tmp_path)
    with patch.object(pipeline,'verify_package'),patch.object(pipeline,'ensure_new'),patch.object(pipeline,'cli',return_value={'result':{'id':'0Af000000000001AAA'}}) as cli:
        result=pipeline.deploy(bundle,dry_run=True)
    args=cli.call_args.args[0]
    assert '--async' in args and '--wait' not in args and '--dry-run' in args
    assert result['result']['done'] is False and result['result']['id']=='0Af000000000001AAA'


def test_async_validation_then_report_unlocks_only_exact_hash(client):
    plan=main.plan_store.get('PLAN-old');plan.status='APPROVED'
    for item in plan.items:item.approval='APPROVED'
    bundle=main.metadata_spec_store.get_package('PLAN-old');bundle['state']='generated';bundle['approvedHash']=bundle['sourceHash']
    main.metadata_spec_store.save_package(bundle)
    with patch.object(main.default_pipeline,'verify_package'),patch.object(main.default_pipeline,'assert_plan'),patch.object(main.layout_workflow,'require',return_value={}),patch.object(main.default_pipeline,'check_tests'),patch.object(main.default_pipeline,'deploy',return_value={'result':{'id':'0Af000000000001AAA','done':False,'status':'Pending'}}):
        response=client.post('/api/plans/PLAN-old/validate')
    assert response.status_code==200 and response.json()['state']=='pending' and response.json()['validatedHash'] is None
    with patch.object(main.default_pipeline,'check_tests'),patch.object(main.default_pipeline,'report',return_value={'result':{'id':'0Af000000000001AAA','done':True,'success':True}}):
        response=client.post('/api/plans/PLAN-old/report')
    assert response.status_code==200 and response.json()['state']=='validated'
    assert response.json()['validatedHash']==bundle['sourceHash']
