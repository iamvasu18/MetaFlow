import json
import io
import zipfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import Mock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from Backend.AI.app.api.apex_api import ApexWorkflow
from Backend.AI.app.services.apex_service import ApexAutomationService, ApexRequest
from Backend.AI.app.services.apex_store import ApexStore
from Backend.AI.app.services.apex_validator import validate_apex_source
from Backend.AI.app.services.apex_generator import generate_apex
from Backend.AI.app.services.metadata_validator import SalesforceMetadataValidator
from Backend.AI.app.validators.plan_validator import ImplementationPlan

CONTEXT = {'objects':[{'name':'Contact','fields':[{'name':'Id'},{'name':'LastName'},{'name':'Email'}]}]}
SOURCE = {'classes':[
    {'name':'ContactSearchService','apex_kind':'Controller','body':"public with sharing class ContactSearchService { @AuraEnabled(cacheable=true) public static List<Contact> search(String term) { if (String.isBlank(term)) { return new List<Contact>(); } String pattern = '%' + term.trim() + '%'; return [SELECT Id, LastName, Email FROM Contact WHERE LastName LIKE :pattern WITH USER_MODE ORDER BY LastName LIMIT 50]; } }"},
    {'name':'ContactSearchServiceTest','apex_kind':'Test','body':"@IsTest private class ContactSearchServiceTest { @IsTest static void searchWorks() { insert new Contact(LastName='Test'); Test.startTest(); List<Contact> found = ContactSearchService.search('Test'); Test.stopTest(); System.assertEquals(1,found.size()); } }"}], 'triggers':[]}

@pytest.fixture
def service(tmp_path):
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}',encoding='utf-8')
    metadata=Mock();metadata.get_context.return_value=deepcopy(CONTEXT);metadata.find_relevant_objects.return_value=['Contact']
    # Org transport is mocked; dedicated discovery tests exercise retrieval.
    return ApexAutomationService(tmp_path,metadata_factory=lambda org:metadata,rule_discovery=lambda context,org,version:deepcopy(context))

def provider(source=SOURCE):
    value=Mock();value.generate.return_value=json.dumps(source);return value

def request(**kwargs):
    return ApexRequest(class_name='ContactSearchService',requirement='Search Contacts',objects=['Contact'],**kwargs)

def success():
    return {'result':{'id':'0Af000000000001AAA','done':True,'success':True,'details':{'runTestResult':{'numTestsRun':2,'numFailures':0}}}}

def test_generate_complete_package_and_optional_access(service):
    p=provider();bundle=service.generate(request(permission_set_name='ContactSearchAccess'),p)
    assert bundle['testClasses']==['ContactSearchServiceTest']
    assert bundle['apiVersion']=='67.0'
    assert len(bundle['files'])==5
    assert 'Not run' in bundle['localChecks']['compilation']
    assert 'ContactSearchService' in bundle['files']['force-app/main/default/permissionsets/ContactSearchAccess.permissionset-meta.xml']
    with zipfile.ZipFile(io.BytesIO(service.archive(bundle))) as archive:
        assert 'sfdx-project.json' in archive.namelist()
    assert 'verifiedContext' in json.loads(p.generate.call_args.kwargs['user_prompt'])

@pytest.mark.parametrize('bad',[
    SOURCE['classes'][0]['body'].replace('with sharing','without sharing'),
    SOURCE['classes'][0]['body'].replace('WITH USER_MODE','WITH SYSTEM_MODE'),
    SOURCE['classes'][0]['body'].replace('WITH USER_MODE',''),
    "public with sharing class ContactSearchService { public static void run() { Database.query('SELECT Id FROM Contact'); } }",
    "public with sharing class ContactSearchService { public static void run() { for (Integer i=0;i<2;i++) { if(i==1) { insert new Contact(LastName='X'); } } } }",
])
def test_policy_rejections_after_bounded_repairs(service,bad):
    data=deepcopy(SOURCE);data['classes'][0]['body']=bad;p=provider(data)
    with pytest.raises(ValueError,match='after 3 attempts'):
        service.generate(request(),p)
    assert p.generate.call_count==3

def test_repairs_source_once(service):
    invalid=deepcopy(SOURCE);invalid['classes'][0]['body']='public class Wrong {}'
    p=Mock();p.generate.side_effect=[json.dumps(invalid),json.dumps(SOURCE)]
    assert service.generate(request(),p)['state']=='generated'
    assert p.generate.call_count==2
    assert 'validationErrors' in json.loads(p.generate.call_args.kwargs['user_prompt'])['repair']

@pytest.mark.parametrize('change', ['duplicate','no_test','see_all','no_assert'])
def test_package_test_contract(service,change):
    data=deepcopy(SOURCE)
    if change=='duplicate': data['classes'][1]['name']='ContactSearchService'
    if change=='no_test': data['classes']=data['classes'][:1]
    if change=='see_all': data['classes'][1]['body']=data['classes'][1]['body'].replace('@IsTest private','@IsTest(SeeAllData=true) private')
    if change=='no_assert': data['classes'][1]['body']=data['classes'][1]['body'].replace('System.assertEquals(1,found.size());','')
    with pytest.raises(ValueError): service.generate(request(),provider(data))

def test_declared_comment_cannot_spoof_class():
    errors,_=validate_apex_source('ApexClass','Good',{'apexKind':'Service','body':'// class Good {}\npublic with sharing class Bad {}'})
    assert any('does not match' in error for error in errors)

def test_comment_delimiters_do_not_break_valid_source():
    errors,_=validate_apex_source('ApexClass','Good',{'apexKind':'Service','body':"public with sharing class Good { // { ([\n String s='}'; /* } ] */ }"})
    assert not errors

@pytest.mark.parametrize('body',["public class Good { ] }","public class Good { /* broken","public class Good { String s='broken; }"])
def test_lexical_errors(body):
    assert validate_apex_source('ApexClass','Good',{'apexKind':'Service','body':body})[0]

def test_unsupported_metadata_type():
    assert validate_apex_source('Flow','Good',{})[0]

def test_actual_apex_source_is_validated_not_skipped(service):
    raw={'id':'I1','action':'CREATE','metadataType':'ApexClass','fullName':'Good','config':{'apexKind':'Service','body':'public with sharing class Good {}'}}
    plan=ImplementationPlan.model_validate({'id':'P1','requirementId':'R1','summary':'Test','status':'APPROVED','items':[raw]})
    validator=SalesforceMetadataValidator(service.project_root)
    assert validator.validate(plan)['valid'] is False
    path=generate_apex(plan.items[0],service.project_root)
    assert validator.validate(plan)['valid'] is True
    path.write_text('public class Bad {}',encoding='utf-8')
    assert validator.validate(plan)['valid'] is False

@pytest.mark.parametrize('version',['oops','0.0','67.0</apiVersion>'])
def test_invalid_api_version_is_rejected(service,version):
    (service.project_root/'sfdx-project.json').write_text(json.dumps({'sourceApiVersion':version}))
    with pytest.raises(ValueError): service.version()

def test_cli_requires_tests_and_both_source_dirs(service):
    bundle=service.generate(request(),provider())
    service.cli=Mock(side_effect=[{'result':[]},success()])
    service.deploy(bundle,dry_run=True)
    args=service.cli.call_args.args[0]
    assert args[args.index('--test-level')+1]=='RunSpecifiedTests'
    assert args[args.index('--tests')+1]=='ContactSearchServiceTest'
    assert '--dry-run' in args
    assert Path(args[args.index('--source-dir')+1]).parts[-3:] == ('force-app', 'main', 'default')

def test_existing_test_name_blocks_deploy(service):
    bundle=service.generate(request(),provider())
    service.cli=Mock(return_value={'result':[{'fullName':'ContactSearchServiceTest'}]})
    with pytest.raises(ValueError,match='already exists'):service.deploy(bundle)

def test_no_executed_tests_rejected(service):
    bundle=service.generate(request(),provider());payload=success();payload['result']['details']['runTestResult']['numTestsRun']=0
    service.cli=Mock(side_effect=[{'result':[]},payload])
    with pytest.raises(ValueError,match='executed'):service.deploy(bundle)

@pytest.fixture
def workflow(service,tmp_path):
    return ApexWorkflow(tmp_path,provider_factory=provider,service=service,allowed_orgs=['AIOrg'],api_token='')

def client(workflow):
    app=FastAPI();app.include_router(workflow.router);return TestClient(app)

def create(workflow):
    result=client(workflow).post('/api/apex/generate',json=request().model_dump())
    assert result.status_code==200,result.text
    return result.json()

def test_api_approval_and_dryrun_before_deployment(workflow):
    bundle=create(workflow);c=client(workflow);url=f'/api/apex/bundles/{bundle["id"]}/deploy'
    assert c.post(url,json={'approved':True,'source_hash':'wrong'}).status_code==422
    workflow.service.cli=Mock(side_effect=[{'result':[]},success(),{'result':[]},success()])
    result=c.post(url,json={'approved':True,'source_hash':bundle['sourceHash']})
    assert result.status_code==200,result.text
    assert result.json()['state']=='deployed'
    deploy_calls=[call.args[0] for call in workflow.service.cli.call_args_list if call.args[0][:3]==['project','deploy','start']]
    assert '--dry-run' in deploy_calls[0] and '--dry-run' not in deploy_calls[1]
    assert c.post(url,json={'approved':True,'source_hash':bundle['sourceHash']}).status_code==409

def test_api_no_tests_prevents_real_deploy(workflow):
    bundle=create(workflow);bad=success();bad['result']['details']['runTestResult']['numTestsRun']=0
    workflow.service.cli=Mock(side_effect=[{'result':[]},bad])
    result=client(workflow).post(f'/api/apex/bundles/{bundle["id"]}/deploy',json={'approved':True,'source_hash':bundle['sourceHash']})
    assert result.status_code==422
    assert workflow.service.cli.call_count==2

def test_pending_validation_and_report(workflow):
    bundle=create(workflow);workflow.service.cli=Mock(side_effect=[{'result':[]},{'result':{'id':'0Af000000000001AAA','done':False,'success':False}}])
    c=client(workflow);base=f'/api/apex/bundles/{bundle["id"]}'
    assert c.post(base+'/validate').json()['state']=='pending'
    assert c.post(base+'/validate').status_code==409
    workflow.service.cli=Mock(return_value=success())
    assert c.post(base+'/report').json()['state']=='validated'

def test_api_auth_org_and_persistence(workflow):
    bundle=create(workflow)
    assert ApexStore(workflow.store.path).get(bundle['id'])['sourceHash']==bundle['sourceHash']
    data=request().model_dump();data['target_org']='Other'
    assert client(workflow).post('/api/apex/generate',json=data).status_code==403
    workflow.api_token='secret'
    assert client(workflow).get('/api/apex/bundles/missing').status_code==401
    assert client(workflow).get('/api/apex/bundles/missing',headers={'Authorization':'Bearer secret'}).status_code==404

def test_store_blocks_overlapping_helper_names(tmp_path):
    store=ApexStore(tmp_path/'apex.sqlite3')
    for name in ['One','Two']:
        store.put({'id':name,'componentName':name,'targetOrg':'AIOrg','state':'generated','components':[{'metadataType':'ApexClass','fullName':'SharedHelper'}]})
    store.claim('One','deploy')
    with pytest.raises(ValueError,match='Another saved'):store.claim('Two','deploy')

def test_trigger_package_generates_both_directories(service):
    data=deepcopy(SOURCE)
    data['triggers']=[{'name':'ContactDescriptionTrigger','sobject':'Contact','events':['before insert'],'body':"trigger ContactDescriptionTrigger on Contact (before insert) { for (Contact record : Trigger.new) { record.Description = 'New'; } }"}]
    bundle=service.generate(request(),provider(data))
    assert 'force-app/main/default/triggers/ContactDescriptionTrigger.trigger' in bundle['files']
    assert any(item['metadataType']=='ApexTrigger' for item in bundle['components'])

def test_unverified_trigger_object_rejected(service):
    data=deepcopy(SOURCE)
    data['triggers']=[{'name':'AccountTrigger','sobject':'Account','events':['before insert'],'body':'trigger AccountTrigger on Account (before insert) {}'}]
    with pytest.raises(ValueError,match='not verified'):service.generate(request(),provider(data))

def test_old_api_version_rejected(service):
    (service.project_root/'sfdx-project.json').write_text('{"sourceApiVersion":"57.0"}')
    with pytest.raises(ValueError,match='>=58.0'):service.generate(request(),provider())

def test_aura_method_in_comment_not_required_by_plain_service(service):
    data=deepcopy(SOURCE);data['classes'][0]['apex_kind']='Service'
    assert service.generate(request(),provider(data))['state']=='generated'

def test_unknown_outcome_blocks_retry(workflow):
    bundle=create(workflow);workflow.service.cli=Mock(side_effect=RuntimeError('timeout'))
    base=f'/api/apex/bundles/{bundle["id"]}/validate'
    assert client(workflow).post(base).status_code==502
    assert workflow.store.get(bundle['id'])['state']=='unknown'
    assert client(workflow).post(base).status_code==409

def test_controller_requires_lwc_callable_method(service):
    data=deepcopy(SOURCE)
    data['classes'][0]['body']=data['classes'][0]['body'].replace('public static List<Contact>','public List<Contact>')
    with pytest.raises(ValueError,match='static @AuraEnabled'):service.generate(request(),provider(data))

def test_real_deploy_timeout_does_not_report_old_validation_job(workflow):
    bundle=create(workflow)
    workflow.store.finish(bundle['id'],state='validated',jobId='0Af000000000002AAA')
    workflow.service.cli=Mock(side_effect=[{'result':[]},success(),{'result':[]},RuntimeError('timeout')])
    response=client(workflow).post(f'/api/apex/bundles/{bundle["id"]}/deploy',json={'approved':True,'source_hash':bundle['sourceHash']})
    assert response.status_code==502
    saved=workflow.store.get(bundle['id'])
    assert saved['state']=='unknown' and saved['jobId'] is None
    assert client(workflow).post(f'/api/apex/bundles/{bundle["id"]}/report').status_code==422

def test_real_deploy_unverified_test_result_is_unknown(service):
    bundle=service.generate(request(),provider());bad=success();bad['result']['details']['runTestResult']['numTestsRun']=0
    service.cli=Mock(side_effect=[{'result':[]},bad])
    with pytest.raises(RuntimeError,match='inspect org status'):service.deploy(bundle,dry_run=False)

@pytest.mark.parametrize('declaration',['with sharing class Good {}','private with sharing class Good {}'])
def test_non_test_class_requires_public_visibility(declaration):
    errors,_=validate_apex_source('ApexClass','Good',{'apexKind':'Service','body':declaration})
    assert any('public or global visibility' in error for error in errors)

def test_private_test_class_remains_valid():
    errors,_=validate_apex_source('ApexClass','GoodTest',{'apexKind':'Test','body':'@IsTest private class GoodTest { @IsTest static void check() { System.assert(true); } }'})
    assert not errors

def test_dml_failure_cannot_return_attempted_count(service):
    data=deepcopy(SOURCE)
    data['classes'][0]['apex_kind']='Service'
    data['classes'][0]['body']='public with sharing class ContactSearchService { public static Integer run(List<Contact> rows) { try { update as user rows; return rows.size(); } catch (DmlException e) { return rows.size(); } } }'
    with pytest.raises(ValueError,match='must propagate failure'):service.generate(request(),provider(data))

def test_generation_repairs_missing_class_visibility(service):
    invalid=deepcopy(SOURCE)
    invalid['classes'][0]['body']=invalid['classes'][0]['body'].replace('public with sharing class','with sharing class')
    p=Mock();p.generate.side_effect=[json.dumps(invalid),json.dumps(SOURCE)]
    assert service.generate(request(),p)['state']=='generated'
    assert 'public or global visibility' in json.loads(p.generate.call_args.kwargs['user_prompt'])['repair']['validationErrors']
