"""Regressions for reported compiler mistakes, stale context and coupled source."""
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from Backend.AI.app.services.apex_validator import validate_apex_source
from Backend.AI.app.services.lwc_apex_contract import controller_contract
from Backend.AI.app.services.conversation_service import ConversationTurn, respond
from Backend.AI.app.salesforce.context_selector import compact_planning_context

BASE='force-app/main/default/classes/'
CONTROLLER="public with sharing class AccountController { @AuraEnabled(cacheable=true) public static List<Account> getAccounts() { return [SELECT Id, Name, Phone FROM Account WITH USER_MODE LIMIT 5]; } }"
TEST="@IsTest private class AccountControllerTest { @IsTest static void findsAccounts() { insert new Account(Name='Test'); Test.startTest(); List<Account> rows=AccountController.getAccounts(); Test.stopTest(); System.Assert.areEqual(1, rows.size()); } }"

@pytest.mark.parametrize('snippet,problem',[
 ('System.Assert.assertEquals(1,1);','Assert class'),
 ('System.Assert.assertNotNull(new Account());','Assert class'),
 ('List<Account> a=[SELECT Id FROM Account WHERE CreatedDate < NOW() WITH USER_MODE];','NOW()'),
 ('throw new Exception();','cannot be constructed'),
 ('@future public void updateCases(List<Id> ids) {}','static'),
 ('@future public static void updateCases(List<Case> records) {}','primitive'),
])
def test_known_compiler_mistakes_block_submission(snippet,problem):
    code='public with sharing class Good { '+snippet+' }'
    errors,_=validate_apex_source('ApexClass','Good',{'apexKind':'Service','body':code})
    assert any(problem in error for error in errors)

def test_valid_bind_assert_and_future_are_not_rejected():
    code="public with sharing class Good { @future public static void work(List<Id> ids) { Datetime cutoff=System.now(); List<Account> rows=[SELECT Id FROM Account WHERE CreatedDate < :cutoff WITH USER_MODE LIMIT 5]; } }"
    assert not validate_apex_source('ApexClass','Good',{'apexKind':'Standard','body':code})[0]
    comment="public with sharing class Good { String s='new Exception(); NOW() System.Assert.assertEquals'; /* new Exception(); */ }"
    assert not validate_apex_source('ApexClass','Good',{'apexKind':'Service','body':comment})[0]

def test_async_test_needs_execution_boundary():
    code='@IsTest private class Good { @IsTest static void testJob() { System.enqueueJob(new Work()); System.Assert.isNotNull(1); } }'
    assert any('startTest' in e for e in validate_apex_source('ApexClass','Good',{'apexKind':'Test','body':code})[0])

def test_verified_controller_contract_is_derived_from_source():
    methods=controller_contract({BASE+'AccountController.cls':CONTROLLER},['AccountController'])
    assert methods['AccountController.getAccounts']['cacheable']
    assert methods['AccountController.getAccounts']['returnType']=='List<Account>'
    with pytest.raises(ValueError,match='no public'):
        controller_contract({BASE+'AccountController.cls':CONTROLLER.replace('@AuraEnabled(cacheable=true)','')},['AccountController'])
    with pytest.raises(ValueError,match='read-only'):
        controller_contract({BASE+'AccountController.cls':CONTROLLER.replace('return [','insert new Account(); return [')},['AccountController'])

def test_nested_controller_methods_are_not_exposed_as_outer_methods():
    code='public with sharing class Outer { public class Inner { @AuraEnabled public static void run() {} } }'
    with pytest.raises(ValueError,match='no public'):
        controller_contract({BASE+'Outer.cls':code},['Outer'])

@pytest.mark.parametrize('message',[
 'Create object Samsung_Service_Request__c with customer, status and cost fields',
 'Create an Apex class GetAccounts that returns five Account names',
 'Build an LWC to show five Accounts',
 'Create a Flow that sets Account Rating to Hot when Industry is Technology',
 'Create a validation rule on Account to require Phone',
 'Create a Permission Set granting read access to Account',
])
def test_complete_new_requests_discard_old_question_context(message):
    provider=Mock();provider.generate.return_value=json.dumps({'action':'build','requirement':message})
    result=respond(ConversationTurn(target_org='owned',message=message,pending_requirement='Create Samsung',pending_question='Reuse Samsung?',reference_context='Old Account count',recent_messages=[{'role':'assistant','content':'Reuse Samsung?'}]),provider,lambda:None)
    assert result['action']=='build'
    payload=json.loads(provider.generate.call_args.kwargs['user_prompt'])
    assert payload['pendingRequirement']==payload['pendingQuestion']==payload['referenceContext']==''
    assert payload['recentMessages']==[]

def test_service_appointment_projection_keeps_required_facts_not_describe_noise():
    original={'objects':[{'name':'ServiceAppointment','label':'Service Appointment','fields':[{'name':'Id','type':'id','unused':'x'*300000},{'name':'EndTime','type':'datetime','unused':'x'*300000},{'name':'Status','type':'picklist','picklistValues':[{'value':'Dispatched','active':True},{'value':'Completed','active':True}]}]}]}
    projected=compact_planning_context('Scheduled Apex for ServiceAppointment EndTime and Status',original)
    assert len(json.dumps(projected)) < 3000
    assert projected['objects'][0]['fields'][2]['picklistValues'][1]['value']=='Completed'
    assert original['objects'][0]['fields'][0]['unused']

def test_integrated_lwc_apex_and_tests_are_one_package(tmp_path):
    from Backend.AI.app.services.metadata_service import DefaultMetadataPipeline, DefaultGenerationRequest
    from Backend.AI.app.services.lwc_service import LWCAutomationService
    from Backend.AI.app.validators.plan_validator import ImplementationPlan
    root=Path(__file__).resolve().parents[4]
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    context={'objects':[{'name':'Account','fields':[{'name':'Id'},{'name':'Name'},{'name':'Phone'}]}], 'existingComponents':{'ApexClass':[],'LightningComponentBundle':[]}, 'validationRuleDiscovery':{'status':'complete'}}
    metadata=Mock();metadata.get_context.return_value=deepcopy(context);metadata.find_relevant_objects.return_value=['Account']
    service=DefaultMetadataPipeline(tmp_path,metadata_factory=lambda org:metadata,rule_discovery=lambda ctx,*args:ctx,lwc_service=LWCAutomationService(tmp_path,metadata_factory=lambda org:metadata,tooling_root=root))
    plan=ImplementationPlan.model_validate({'id':'P','requirementId':'R','summary':'Accounts','status':'DRAFT','items':[
        {'id':'C','action':'CREATE','metadataType':'ApexClass','fullName':'AccountController','config':{'apexKind':'Controller'}},
        {'id':'T','action':'CREATE','metadataType':'ApexClass','fullName':'AccountControllerTest','config':{'apexKind':'Test'},'dependencies':['C']},
        {'id':'L','action':'CREATE','metadataType':'LightningComponentBundle','fullName':'accountList','config':{'componentKind':'LWC','targets':['lightning__AppPage']},'dependencies':['C']}]})
    js="import { LightningElement, wire } from 'lwc'; import getAccounts from '@salesforce/apex/AccountController.getAccounts'; export default class AccountList extends LightningElement { @wire(getAccounts) accounts; }"
    provider=Mock();provider.generate.side_effect=[json.dumps({'classes':[{'name':'AccountController','apex_kind':'Controller','body':CONTROLLER},{'name':'AccountControllerTest','apex_kind':'Test','body':TEST}],'triggers':[]}),json.dumps({'html':'<template><p>Accounts</p></template>','javascript':js,'css':''})]
    with patch.object(service,'discover',return_value=(metadata,context)),patch('Backend.AI.app.services.metadata_service.connected_api',return_value=None),patch('Backend.AI.app.services.apex_service.connected_api',return_value=None),patch('Backend.AI.app.services.metadata_service.PlanningService.generate_plan',return_value=plan):
        package=service.generate(DefaultGenerationRequest(requirement='Build an Account LWC with an Apex controller',target_org='owned'),provider)
    assert package['testClasses']==['AccountControllerTest']
    assert len(package['components'])==3 and package['sourceHash']
    assert BASE+'AccountController.cls' in package['files']
    assert 'force-app/main/default/lwc/accountList/accountList.js' in package['files']
    assert not package.get('approvedHash')
    assert 'AccountController.getAccounts' in json.loads(provider.generate.call_args.kwargs['user_prompt'])['verifiedApexMethods']

@pytest.mark.parametrize('formula',['Status__c = "Closed"','"Closed" = Status__c','ISBLANK(Status__c)'])
def test_picklist_misuse_identifies_rule_not_all_fields(formula):
    from Backend.AI.app.services.formula_policy import validate_picklist_formulas
    plan={'items':[{'metadataType':'ValidationRule','fullName':'Bank__c.ClosedDate','action':'CREATE','config':{'errorConditionFormula':formula}}]}
    context={'objects':[{'name':'Bank__c','fields':[{'name':'Status__c','type':'picklist'}]}]}
    with pytest.raises(ValueError,match='Bank__c.ClosedDate'):
        validate_picklist_formulas(plan,context)
    plan['items'][0]['config']['errorConditionFormula']='AND(ISPICKVAL(Status__c, "Closed"), ISBLANK(ClosedDate__c))'
    validate_picklist_formulas(plan,context)

@pytest.mark.parametrize('kind,implementation,call',[
 ('Queueable','implements Queueable { public void execute(QueueableContext ctx) {} }','System.enqueueJob(new Work());'),
 ('Batchable','implements Database.Batchable<SObject> { public Database.QueryLocator start(Database.BatchableContext ctx) { return Database.getQueryLocator([SELECT Id FROM Account WITH USER_MODE]); } public void execute(Database.BatchableContext ctx, List<SObject> scope) {} public void finish(Database.BatchableContext ctx) {} }','Database.executeBatch(new Work(),200);'),
 ('Schedulable','implements Schedulable { public void execute(SchedulableContext ctx) {} }',"System.schedule('WorkTest','0 0 0 1 1 ? 2099',new Work());"),
 ('Standard','{ @future public static void work(List<Id> ids) {} }','Work.work(new List<Id>());'),
])
def test_async_package_tests_call_real_entry_points(kind,implementation,call):
    from Backend.AI.app.services.apex_service import ApexAutomationService,ApexSources,ApexRequest
    def source(test_body):
        return ApexSources.model_validate({'classes':[{'name':'Work','apex_kind':kind,'body':'public with sharing class Work '+implementation},{'name':'WorkTest','apex_kind':'Test','body':test_body}],'triggers':[]})
    good='@IsTest private class WorkTest { @IsTest static void runs() { Test.startTest(); '+call+' Test.stopTest(); System.Assert.isTrue(true); } }'
    service=ApexAutomationService()
    service.check_sources(ApexRequest(class_name='Work',requirement='Run async work'),source(good),{'objects':[]})
    bad='@IsTest private class WorkTest { @IsTest static void runs() { System.Assert.isTrue(true); } }'
    with pytest.raises(ValueError,match='companion tests'):
        service.check_sources(ApexRequest(class_name='Work',requirement='Run async work'),source(bad),{'objects':[]})


def coupled_package():
    js="import { LightningElement, wire } from 'lwc'; import getAccounts from '@salesforce/apex/AccountController.getAccounts'; export default class AccountList extends LightningElement { @wire(getAccounts) accounts; }"
    return {'sourceHash':'a'*64,'requirement':'Show five Accounts using the controller','targetOrg':'owned','apiVersion':'67.0','state':'failed','testClasses':['AccountControllerTest','OtherTest'],
        'components':[{'metadataType':kind,'fullName':name} for kind,name in [('ApexClass','AccountController'),('ApexClass','AccountControllerTest'),('ApexClass','Other'),('ApexClass','OtherTest'),('LightningComponentBundle','accountList')]],
        'plan':{'items':[{'id':'C','metadataType':'ApexClass','fullName':'AccountController','config':{'apexKind':'Controller'}},{'id':'T','metadataType':'ApexClass','fullName':'AccountControllerTest','config':{'apexKind':'Test'},'dependencies':['C']},{'id':'O','metadataType':'ApexClass','fullName':'Other','config':{'apexKind':'Standard'}},{'id':'OT','metadataType':'ApexClass','fullName':'OtherTest','config':{'apexKind':'Test'},'dependencies':['O']},{'id':'L','metadataType':'LightningComponentBundle','fullName':'accountList','dependencies':['C']} ]},
        'files':{BASE+'AccountController.cls':CONTROLLER,BASE+'AccountControllerTest.cls':TEST,BASE+'Other.cls':'public with sharing class Other {}',BASE+'OtherTest.cls':'@IsTest private class OtherTest { @IsTest static void run() { Other value=new Other(); System.Assert.isNotNull(value); } }','force-app/main/default/lwc/accountList/accountList.js':js,'force-app/main/default/lwc/accountList/accountList.html':'<template><p>Accounts</p></template>'}}

@pytest.mark.parametrize('selected',['AccountController','AccountControllerTest','accountList'])
def test_repair_scope_coordinates_controller_test_and_lwc_without_unrelated_classes(selected):
    from Backend.AI.app.services.component_source_service import repair_files
    files=repair_files(coupled_package(),selected)
    assert BASE+'AccountController.cls' in files
    assert BASE+'AccountControllerTest.cls' in files
    assert 'force-app/main/default/lwc/accountList/accountList.js' in files
    assert BASE+'Other.cls' not in files and BASE+'OtherTest.cls' not in files

def test_ai_repair_cannot_break_the_saved_lwc_controller_connection():
    from Backend.AI.app.services.component_source_service import repair_sources
    package=coupled_package();before=deepcopy(package)
    provider=Mock();provider.generate.return_value=json.dumps({'files':{BASE+'AccountController.cls':CONTROLLER.replace('getAccounts','fetchAccounts')}})
    with pytest.raises(ValueError,match='Unverified Apex controller method'):
        repair_sources(package,'AccountController','Rename getAccounts to fetchAccounts across this controller and its LWC',provider)
    assert provider.generate.call_count==3
    assert package==before

def test_coordinated_ai_repair_passes_source_and_real_lwc_checks():
    from Backend.AI.app.services.component_source_service import repair_sources
    package=coupled_package();before=deepcopy(package)
    path='force-app/main/default/lwc/accountList/accountList.js'
    replacements={BASE+'AccountController.cls':CONTROLLER.replace('getAccounts','fetchAccounts'),BASE+'AccountControllerTest.cls':TEST.replace('getAccounts','fetchAccounts'),path:package['files'][path].replace('getAccounts','fetchAccounts')}
    provider=Mock();provider.generate.return_value=json.dumps({'files':replacements})
    assert repair_sources(package,'AccountController','Rename this method across the controller, its tests and LWC',provider)==replacements
    assert provider.generate.call_count==1 and package==before

def test_phase_logs_preserve_timing_without_prompt_or_credentials():
    import logging
    from Backend.AI.app.services.observability import JsonFormatter
    record=logging.LogRecord('test',logging.INFO,'',0,'client_secret=do-not-log',(),None)
    record.event='salesforce_phase_finished';record.phase='submit';record.duration_ms=123
    record.client_secret='do-not-log';record.prompt='private source'
    result=json.loads(JsonFormatter().format(record))
    assert result['phase']=='submit' and result['duration_ms']==123
    assert 'do-not-log' not in json.dumps(result) and 'prompt' not in result

@pytest.mark.parametrize('statement,problem',[
 ('update rows;','as user'),
 ('Database.update(rows);','AccessLevel.USER_MODE'),
 ('for(Account row:rows) { System.enqueueJob(new Work()); }','outside record loops'),
 ('if(Test.isRunningTest()) { return; }','Production behavior'),
])
def test_generation_source_policy_blocks_known_security_and_bulk_bypasses(statement,problem):
    from Backend.AI.app.services.apex_service import ApexAutomationService,ApexSources,ApexRequest
    source=ApexSources.model_validate({'classes':[{'name':'Good','apex_kind':'Standard','body':'public with sharing class Good { public static void run(List<Account> rows) { '+statement+' } }'},{'name':'GoodTest','apex_kind':'Test','body':'@IsTest private class GoodTest { @IsTest static void run() { System.Assert.isNotNull(new Account()); } }'}],'triggers':[]})
    with pytest.raises(ValueError,match=problem):
        ApexAutomationService().check_sources(ApexRequest(class_name='Good',requirement='Update records'),source,{'objects':[]})

@pytest.mark.parametrize('statement',['update as user rows;','Database.update(rows, AccessLevel.USER_MODE);'])
def test_explicit_user_mode_dml_passes_the_source_policy(statement):
    from Backend.AI.app.services.apex_service import ApexAutomationService,ApexSources,ApexRequest
    source=ApexSources.model_validate({'classes':[{'name':'Good','apex_kind':'Standard','body':'public with sharing class Good { public static void run(List<Account> rows) { '+statement+' } }'},{'name':'GoodTest','apex_kind':'Test','body':'@IsTest private class GoodTest { @IsTest static void run() { System.Assert.isNotNull(new Account()); } }'}],'triggers':[]})
    ApexAutomationService().check_sources(ApexRequest(class_name='Good',requirement='Update records'),source,{'objects':[]})

def test_grounding_cannot_change_explicit_object_to_lwc_or_restart_optional_questions():
    replies=[{'action':'build','requested_type':'CustomObject','requirement':'Create Samsung_Service_Request__c with a Text customer field','objects':['Samsung_Service_Request__c'],'create_new':True}, {'action':'clarify','requested_type':'LightningComponentBundle','requirement':'Build a Samsung LWC','blocking_detail':'behavior','response':'What should the component do?'}]
    provider=Mock();provider.generate.side_effect=[json.dumps(row) for row in replies]
    class Api:
        def list_objects(self):return []
    result=respond(ConversationTurn(target_org='owned',message='Create object Samsung_Service_Request__c with a customer Text field'),provider,lambda:Api())
    assert result['action']=='build' and result['requested_type']=='CustomObject'
    assert 'Samsung_Service_Request__c' in result['requirement'] and 'LWC' not in result['requirement']

def test_ai_timeout_is_bounded_and_does_not_retry_or_expose_request(monkeypatch):
    from Backend.AI.app.providers import ai_provider
    monkeypatch.delenv('AI_REQUEST_TIMEOUT_SECONDS',raising=False)
    provider_client=Mock()
    provider_client.messages.count_tokens.return_value=Mock(input_tokens=10)
    provider_client.messages.create.side_effect=ai_provider.anthropic.APIConnectionError(request=Mock())
    monkeypatch.setattr(ai_provider.anthropic,'Anthropic',Mock(return_value=provider_client))
    provider=ai_provider.AnthropicProvider(api_key='private-key',model='model')
    assert ai_provider.anthropic.Anthropic.call_args.kwargs['max_retries']==0
    assert ai_provider.anthropic.Anthropic.call_args.kwargs['timeout']==90
    with pytest.raises(RuntimeError,match='timed out') as error:
        provider.generate('private source','private requirement')
    assert provider_client.messages.create.call_count==1
    assert 'private-key' not in str(error.value) and 'private source' not in str(error.value)
