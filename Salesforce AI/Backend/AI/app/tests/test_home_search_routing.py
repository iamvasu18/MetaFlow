import json
from unittest.mock import Mock
import pytest
from Backend.AI.app.services.implementation_routing import prefers_home_search_lwc, resolve_ui_requirement, check_ui_plan, ImplementationChoiceError
from Backend.AI.app.services.planning_service import PlanningService

REQUEST='create a component on home page, like i want a search button, whenever i search the accounts it will display all accounts, and whenever i open the account it will also display its related opportunities'

def test_home_search_chooses_lwc_preserving_business_behavior():
    requirement=resolve_ui_requirement(REQUEST)
    assert requirement.startswith(REQUEST)
    assert 'lightning__HomePage' in requirement
    assert prefers_home_search_lwc(requirement)
    assert resolve_ui_requirement(requirement)==requirement

@pytest.mark.parametrize('requirement',['Create a Screen Flow on home page to search Account','Create an Apex component on home page to search Account','Can we create a component to search accounts?','When Account Industry is Technology set Rating to Hot'])
def test_explicit_technology_questions_and_automation_are_not_rerouted(requirement):
    assert not prefers_home_search_lwc(requirement)
    assert resolve_ui_requirement(requirement)==requirement

def test_wrong_flow_and_wrong_target_are_rejected():
    with pytest.raises(ImplementationChoiceError):check_ui_plan(REQUEST,{'items':[{'metadataType':'Flow'}]})
    with pytest.raises(ImplementationChoiceError):check_ui_plan(REQUEST,{'items':[{'metadataType':'LightningComponentBundle','config':{'targets':['lightning__AppPage']}}]})
    check_ui_plan(REQUEST,{'items':[{'metadataType':'LightningComponentBundle','config':{'targets':['lightning__HomePage']}}]})

def test_planner_regenerates_wrong_technology_once_before_schema_validation():
    provider=Mock()
    proper={'items':[{'metadataType':'LightningComponentBundle','config':{'targets':['lightning__HomePage']}}]}
    provider.generate.side_effect=[json.dumps({'items':[{'metadataType':'Flow'}]}),json.dumps(proper)]
    service=PlanningService(provider=provider)
    plan=Mock()
    service._validate_generated_plan=Mock(return_value=plan)
    assert service.generate_plan(REQUEST,salesforce_context={'objects':[]}) is plan
    assert provider.generate.call_count==2
    service._validate_generated_plan.assert_called_once()
    assert 'LightningComponentBundle' in provider.generate.call_args.kwargs['system_prompt']

def test_related_list_adapter_passes_real_source_checker(tmp_path):
    from pathlib import Path
    from Backend.AI.app.services.lwc_service import LWCAutomationService, LWCSource
    project=Path(__file__).resolve().parents[4]
    service=LWCAutomationService(tmp_path,tooling_root=project)
    source=LWCSource(html='<template><lightning-record-picker label="Account" object-api-name="Account" value={selectedId} onchange={handleChange}></lightning-record-picker></template>',javascript="import { LightningElement, wire } from 'lwc'; import { getRelatedListRecords } from 'lightning/uiRelatedListApi'; export default class AccountSearch extends LightningElement { selectedId; @wire(getRelatedListRecords, { parentRecordId: '$selectedId', relatedListId: 'Opportunities', fields: ['Opportunity.Name'] }) related; handleChange(event) { this.selectedId = event.detail.recordId; } }",css='')
    context={'objects':[{'name':'Account','fields':[{'name':'Id'},{'name':'Name'}]},{'name':'Opportunity','fields':[{'name':'Name'}]}]}
    assert service.check_source('accountSearch',source,context,'67.0')['valid'] is True

def test_failed_job_stores_message_not_python_dictionary(client):
    from unittest.mock import patch
    from Backend.AI.app.tests.test_workspace_regression import main, accounts
    from Backend.AI.app.tests.test_background_jobs import scoped
    from Backend.AI.app.services import background_jobs as jobs
    with accounts.db() as connection:
        connection.execute('INSERT INTO workspace_conversations VALUES(?,?,?,?,?)',('ui-chat','u','app_ours','Search',0))
    detail={'code':'PLAN_REJECTED','message':'The generated draft failed its component checks.','repairTicket':'saved-ticket'}
    tracked=scoped(jobs.enqueue,'generate',{'request':{'requirement':'Search','target_org':'app_ours','generate_files':True},'conversation_id':'ui-chat'},key='ui-error')
    with patch.object(main,'generate_plan',side_effect=main.HTTPException(422,detail)):
        jobs.process_jobs()
    with accounts.db() as connection:
        content=connection.execute('SELECT content FROM workspace_messages WHERE conversation_id=?',('ui-chat',)).fetchone()[0]
    assert content==detail['message']
    assert jobs.get_owned(tracked['jobId'],'u')['result']['detail']['repairTicket']=='saved-ticket'

from Backend.AI.app.tests.test_workspace_regression import client
