import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from Backend.AI.app.api.lwc_api import LWCWorkflow
from Backend.AI.app.services.lwc_service import LWCAutomationService, LWCRequest, LWCSource
from Backend.AI.app.services.lwc_store import LWCStore

HTML = '<template><lightning-card title="Account"><lightning-record-picker label="Account" object-api-name="Account" value={selectedId} onchange={handleChange}></lightning-record-picker><lightning-button label="Clear" onclick={clearSelection}></lightning-button></lightning-card></template>'
JS = "import { LightningElement, api } from 'lwc'; export default class AccountSearch extends LightningElement { @api recordId; selectedId; handleChange(e) { this.selectedId=e.detail.recordId; } clearSelection() { this.selectedId=null; } }"
CTX = {'objects':[{'name':'Account','fields':[{'name':'Id'},{'name':'Name'}]}]}

@pytest.fixture
def service(tmp_path):
    # Use the real installed checker; no symlinks or admin privileges required.
    project_root = Path(__file__).resolve().parents[4]
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    metadata = Mock()
    metadata.get_context.return_value = deepcopy(CTX)
    metadata.find_relevant_objects.return_value = ['Account']
    return LWCAutomationService(tmp_path,metadata_factory=lambda org:metadata,tooling_root=project_root)

class Provider:
    def generate(self,**kwargs):
        return json.dumps({'html':HTML,'javascript':JS,'css':':host { display:block; }'})

def test_real_ast_lint_compiler_and_verified_discovery(service):
    result=service.generate(LWCRequest(component_name='accountSearch',requirement='Search Account',objects=['Account']),Provider())
    assert result['localChecks']['valid'] is True
    assert result['sourceHash'] and result['targetOrg']=='AIOrg'
    assert 'event.detail.id' not in result['files']['force-app/main/default/lwc/accountSearch/accountSearch.js']

@pytest.mark.parametrize('bad',[
    JS.replace('this.selectedId=e.detail.recordId',"eval('1+1')"),
    JS.replace('this.selectedId=e.detail.recordId',"this.innerHTML='bad'"),
    JS.replace('e.detail.recordId','e.detail.id'),
    JS.replace('extends LightningElement',''),
    JS+' broken( ',
    "import BAD from '@salesforce/schema/Fake__c.Name'; "+JS,
    "import apex from '@salesforce/apex/Fake.method'; "+JS,
    JS.replace('this.selectedId=e.detail.recordId',"fetch('https://example.org')"),
    JS.replace('this.selectedId=e.detail.recordId',"this['innerHTML']='bad'"),
    JS.replace('this.selectedId=e.detail.recordId',"this?.constructor('bad')"),
])
def test_source_rejections_use_real_node_checker(service,bad):
    with pytest.raises(ValueError,match='Generated LWC rejected'):
        service.check_source('accountSearch',LWCSource(html=HTML,javascript=bad),CTX,'67.0')

@pytest.mark.parametrize('html',[
    '<template><iframe src="https://example.org"></iframe></template>',
    '<template><div lwc:dom="manual"></div></template>',
    '<template><lightning-record-view-form object-api-name="Account"><lightning-output-field field-name="Missing__c"></lightning-output-field></lightning-record-view-form></template>',
])
def test_template_policy(service,html):
    with pytest.raises(ValueError):
        service.check_source('accountSearch',LWCSource(html=html,javascript=JS),CTX,'67.0')

@pytest.fixture
def workflow(service,tmp_path):
    return LWCWorkflow(tmp_path,provider_factory=lambda:Provider(),service=service,allowed_orgs=['AIOrg'],api_token='')

def client(workflow):
    app=FastAPI();app.include_router(workflow.router);return TestClient(app)

def generate(workflow):
    response=client(workflow).post('/api/lwc/generate',json={'component_name':'accountSearch','requirement':'Search accounts','objects':['Account']})
    assert response.status_code==200,response.text
    return response.json()

def test_persistence_and_source_bound_approval(workflow):
    bundle=generate(workflow)
    assert LWCStore(workflow.store.path).get(bundle['id'])['sourceHash']==bundle['sourceHash']
    response=client(workflow).post(f'/api/lwc/bundles/{bundle["id"]}/deploy',json={'approved':True,'source_hash':'wrong'})
    assert response.status_code==422

def test_auth_and_org_allowlist(workflow):
    assert client(workflow).post('/api/lwc/generate',json={'component_name':'a','requirement':'test','target_org':'Other'}).status_code==403
    workflow.api_token='secret'
    assert client(workflow).get('/api/lwc/bundles/missing').status_code==401
    assert client(workflow).get('/api/lwc/bundles/missing',headers={'Authorization':'Bearer secret'}).status_code==404

def test_pending_dryrun_never_deploys(workflow):
    bundle=generate(workflow)
    workflow.service.deploy=Mock(return_value={'result':{'id':'0Af000000000001AAA','done':False,'status':'InProgress','success':False}})
    response=client(workflow).post(f'/api/lwc/bundles/{bundle["id"]}/deploy',json={'approved':True,'source_hash':bundle['sourceHash']})
    assert response.status_code==200 and response.json()['state']=='pending'
    assert workflow.service.deploy.call_count==1
    assert client(workflow).post(f'/api/lwc/bundles/{bundle["id"]}/validate').status_code==409
    workflow.service.report=Mock(return_value={'result':{'id':'0Af000000000001AAA','done':True,'success':True}})
    assert client(workflow).post(f'/api/lwc/bundles/{bundle["id"]}/report').json()['state']=='validated'

def test_validation_before_deploy_and_repeat_blocked(workflow):
    bundle=generate(workflow)
    workflow.service.deploy=Mock(return_value={'result':{'id':'0Af000000000001AAA','done':True,'success':True}})
    body={'approved':True,'source_hash':bundle['sourceHash']}
    url=f'/api/lwc/bundles/{bundle["id"]}/deploy'
    assert client(workflow).post(url,json=body).json()['state']=='deployed'
    assert [c.kwargs['dry_run'] for c in workflow.service.deploy.call_args_list]==[True,False]
    assert client(workflow).post(url,json=body).status_code==409

def test_name_collision(service):
    service.cli=Mock(return_value={'result':[{'fullName':'accountSearch'}]})
    with pytest.raises(ValueError,match='already exists'):
        service.ensure_new({'componentName':'accountSearch','targetOrg':'AIOrg','apiVersion':'67.0'})

def test_unknown_result_blocks_retry(workflow):
    bundle=generate(workflow)
    workflow.service.deploy=Mock(side_effect=RuntimeError('timeout'))
    assert client(workflow).post(f'/api/lwc/bundles/{bundle["id"]}/validate').status_code==502
    assert workflow.store.get(bundle['id'])['state']=='unknown'
    assert client(workflow).post(f'/api/lwc/bundles/{bundle["id"]}/validate').status_code==409

def test_store_blocks_simultaneous_same_name(tmp_path):
    store=LWCStore(tmp_path/'db.sqlite3')
    for ident in ['a','b']:
        store.put({'id':ident,'targetOrg':'AIOrg','componentName':'sameName','state':'generated'})
    store.claim('a','deploy')
    with pytest.raises(ValueError,match='Another saved operation'):
        store.claim('b','deploy')

FORM = '<lightning-record-view-form record-id={selectedId} object-api-name="Account" onload={handleLoad}><lightning-output-field field-name="Name"></lightning-output-field></lightning-record-view-form>'
LOADING_JS = """import { LightningElement } from 'lwc';
export default class AccountSearch extends LightningElement {
    selectedId = null;
    isLoading = false;
    get showDetails() { return !this.isLoading; }
    handleLoad() { this.finishLoading(); }
    finishLoading() { this.isLoading = false; }
}"""

@pytest.mark.parametrize('html,message', [
    ('<template>'+FORM.replace('onload=', 'oload=')+'</template>', 'onload, not oload'),
    ('<template><template if:false={isLoading}>'+FORM+'</template></template>', 'must stay mounted'),
    ('<template><template lwc:if={showDetails}>'+FORM+'</template></template>', 'must stay mounted'),
    ('<template><template lwc:if={isLoading}><p>Loading</p></template><template lwc:else>'+FORM+'</template></template>', 'must stay mounted'),
    ('<template><div if:false={isLoading}>'+FORM+'</div></template>', 'must stay mounted'),
])
def test_record_form_lifecycle_rejections(service, html, message):
    with pytest.raises(ValueError, match=message):
        service.check_source('accountSearch', LWCSource(html=html, javascript=LOADING_JS), CTX, '67.0')

def test_spinner_does_not_gate_record_form(service):
    html = '<template><template lwc:if={selectedId}><template lwc:if={isLoading}><lightning-spinner alternative-text="Loading"></lightning-spinner></template>'+FORM+'</template></template>'
    report = service.check_source('accountSearch', LWCSource(html=html, javascript=LOADING_JS, css='.details { position: relative; }'), CTX, '67.0')
    assert report['valid'] is True

def test_slds_override_rejected(service):
    with pytest.raises(ValueError, match='Do not redefine SLDS'):
        service.check_source('accountSearch', LWCSource(html=HTML, javascript=JS, css='.slds-grid { display: grid; }'), CTX, '67.0')

def test_generation_instructions_cover_record_form_lifecycle(service):
    provider = Mock()
    provider.generate.return_value = Provider().generate()
    service.generate(LWCRequest(component_name='accountSearch', requirement='Search Account', objects=['Account']), provider)
    prompt = provider.generate.call_args.kwargs['system_prompt']
    assert 'Keep record forms mounted while loading' in prompt
    assert 'onload, never oload' in prompt
    assert 'Boolean(recordId)' in prompt

def test_original_generated_spinner_bug_rejected(service):
    html = '<template><template if:true={selectedId}><template if:false={isLoading}>'+FORM.replace('onload=', 'oload=')+'</template></template></template>'
    javascript = LOADING_JS.replace('this.finishLoading();', 'this.isLoading = false;')
    with pytest.raises(ValueError, match='onload, not oload'):
        service.check_source('accountSearch', LWCSource(html=html, javascript=javascript), CTX, '67.0')

def test_generation_repairs_invalid_template_then_slds_override(service):
    good = {'html':HTML, 'javascript':JS, 'css':''}
    invalid_template = dict(good, html='<template><template lwc:if={!selectedId}><p>Empty</p></template></template>')
    invalid_css = dict(good, css='.slds-grid { display: grid; }')
    provider = Mock()
    provider.generate.side_effect = [json.dumps(invalid_template), json.dumps(invalid_css), json.dumps(good)]
    bundle = service.generate(LWCRequest(component_name='accountSearch', requirement='Search Account', objects=['Account']), provider)
    assert bundle['localChecks']['valid'] is True
    assert provider.generate.call_count == 3
    second = json.loads(provider.generate.call_args_list[1].kwargs['user_prompt'])
    third = json.loads(provider.generate.call_args_list[2].kwargs['user_prompt'])
    assert 'LWC1060' in second['repair']['validationErrors']
    assert 'Do not redefine SLDS' in third['repair']['validationErrors']
    assert third['requirement'] == 'Search Account'

def test_generation_stops_after_three_invalid_attempts(service):
    provider = Mock()
    provider.generate.return_value = json.dumps({'html':HTML, 'javascript':JS, 'css':'.slds-grid { display: grid; }'})
    with pytest.raises(ValueError, match='after 3 attempts'):
        service.generate(LWCRequest(component_name='accountSearch', requirement='Search Account', objects=['Account']), provider)
    assert provider.generate.call_count == 3

def test_generation_repairs_invalid_json(service):
    provider = Mock()
    provider.generate.side_effect = ['not JSON', Provider().generate()]
    assert service.generate(LWCRequest(component_name='accountSearch', requirement='Search Account'), provider)['localChecks']['valid']
    assert provider.generate.call_count == 2

def test_slds_comment_is_not_an_override(service):
    source = LWCSource(html=HTML, javascript=JS, css='/* Use .slds-grid in HTML. */ .details { position: relative; }')
    assert service.check_source('accountSearch', source, CTX, '67.0')['valid']

def test_unsupported_requirement_is_not_retried(service):
    provider = Mock()
    provider.generate.return_value = '{"unsupported":"Requires Apex"}'
    with pytest.raises(ValueError, match='Unsupported by this LWC'):
        service.generate(LWCRequest(component_name='accountSearch', requirement='Unsupported'), provider)
    assert provider.generate.call_count == 1

def test_nonstring_provider_response_is_repaired(service):
    provider = Mock()
    provider.generate.side_effect = [None, Provider().generate()]
    assert service.generate(LWCRequest(component_name='accountSearch', requirement='Search Account'), provider)['localChecks']['valid']
    assert provider.generate.call_count == 2

APEX_JS="import { LightningElement, wire } from 'lwc'; import getAccounts from '@salesforce/apex/AccountController.getAccounts'; export default class AccountSearch extends LightningElement { @wire(getAccounts) accounts; }"

def test_verified_cacheable_apex_wire_uses_real_compiler(service):
    report=service.check_source('accountSearch',LWCSource(html='<template><p>Accounts</p></template>',javascript=APEX_JS),CTX,'67.0',{'AccountController.getAccounts':{'cacheable':True}})
    assert report['valid']

@pytest.mark.parametrize('methods,source,message',[
 ({},APEX_JS,'Unverified Apex'),
 ({'AccountController.getAccounts':{'cacheable':False}},APEX_JS,'must be cacheable'),
 ({'Other.getAccounts':{'cacheable':True}},APEX_JS,'Unverified Apex'),
 ({'AccountController.getAccounts':{'cacheable':True}},APEX_JS.replace('import getAccounts from','import { getAccounts } from'),'default import'),
])
def test_apex_lwc_import_contract_rejects_invalid_connections(service,methods,source,message):
    with pytest.raises(ValueError,match=message):
        service.check_source('accountSearch',LWCSource(html='<template><p>Accounts</p></template>',javascript=source),CTX,'67.0',methods)

def test_verified_noncacheable_apex_can_be_called_imperatively(service):
    source="import { LightningElement } from 'lwc'; import run from '@salesforce/apex/AccountController.run'; export default class AccountSearch extends LightningElement { error; handleRun() { run().catch(error => { this.error=error; }); } }"
    report=service.check_source('accountSearch',LWCSource(html='<template><lightning-button label="Run" onclick={handleRun}></lightning-button></template>',javascript=source),CTX,'67.0',{'AccountController.run':{'cacheable':False}})
    assert report['valid']

def test_wrong_named_apex_parameter_is_rejected(service):
    source=APEX_JS.replace('@wire(getAccounts)','@wire(getAccounts, {wrongName: "value"})')
    with pytest.raises(ValueError,match='Unknown Apex parameter'):
        service.check_source('accountSearch',LWCSource(html='<template><p>Accounts</p></template>',javascript=source),CTX,'67.0',{'AccountController.getAccounts':{'cacheable':True,'parameterNames':['term']}})

def test_ui_list_read_adapter_is_wire_only(service):
    source="import { LightningElement } from 'lwc'; import { getListRecordsByName } from 'lightning/uiListsApi'; export default class AccountSearch extends LightningElement { load() { return getListRecordsByName({objectApiName:'Account',listViewApiName:'AllAccounts'}); } }"
    with pytest.raises(ValueError,match='must be used with @wire'):
        service.check_source('accountSearch',LWCSource(html='<template><p>Accounts</p></template>',javascript=source),CTX,'67.0')

def test_aliased_wire_cannot_bypass_apex_cacheability_policy(service):
    source=APEX_JS.replace('LightningElement, wire','LightningElement, wire as observe').replace('@wire(', '@observe(')
    with pytest.raises(ValueError,match='must be cacheable'):
        service.check_source('accountSearch',LWCSource(html='<template><p>Accounts</p></template>',javascript=source),CTX,'67.0',{'AccountController.getAccounts':{'cacheable':False}})


def test_imperative_apex_without_error_handler_is_rejected(service):
    source="import { LightningElement } from 'lwc'; import run from '@salesforce/apex/AccountController.run'; export default class AccountSearch extends LightningElement { handleRun() { run().then(result => { this.result=result; }); } }"
    with pytest.raises(ValueError,match='rejection handler'):
        service.check_source('accountSearch',LWCSource(html='<template><lightning-button label="Run" onclick={handleRun}></lightning-button></template>',javascript=source),CTX,'67.0',{'AccountController.run':{'cacheable':False}})


def test_generated_jest_tests_reject_skipped_cases(service):
    source=LWCSource(html='<template><p>Ready</p></template>',javascript="import {LightningElement} from 'lwc'; export default class AccountSearch extends LightningElement {}",tests="test.skip('not executed',()=>{expect(true).toBe(true);});")
    with pytest.raises(ValueError,match='skip or focus'):
        service.check_source('accountSearch',source,CTX,'67.0')


def test_archive_exports_behavior_tests_separately_from_deployable_source(service):
    import io,zipfile,json
    bundle={'componentName':'accountSearch','apiVersion':'67.0','sourceHash':'saved-hash',
        'files':{'force-app/main/default/lwc/accountSearch/accountSearch.js':'source'},
        'verificationFiles':{'force-app/main/default/lwc/accountSearch/__tests__/accountSearch.test.js':'test source'}}
    with zipfile.ZipFile(io.BytesIO(service.archive(bundle))) as archive:
        data=json.loads(archive.read('verification/behavior-tests.json'))
        assert data['sourceHash']=='saved-hash'
        assert data['verificationFiles']==bundle['verificationFiles']
        assert not any('/__tests__/' in name for name in archive.namelist())
