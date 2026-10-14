from copy import deepcopy
from Backend.AI.app.services.flow_entry_policy import complete_missing_entry_filters
from Backend.AI.app.validators.flow_validator import ExtendedFlowConfig


def plan():
    return {'items':[{'metadataType':'Flow','config':{
        'contractVersion':2,'flowType':'RecordTriggered','triggerType':'RecordAfterSave',
        'recordTriggerType':'CreateAndUpdate','object':'Case','status':'Draft',
        'doesRequireRecordChangedToMeetCriteria':True,'startFilters':[],'startElement':'Check',
        'elements':[{'kind':'Decision','name':'Check','label':'Check case','defaultLabel':'No action','defaultNext':None,
            'rules':[{'name':'HighWeb','label':'High web','conditionLogic':'and','conditions':[
                {'field':'$Record.Priority','operator':'EqualTo','value':{'type':'String','value':'High'}},
                {'field':'$Record.Origin','operator':'EqualTo','value':{'type':'String','value':'Web'}}], 'next':'Update'}]},
            {'kind':'UpdateRecordById','name':'Update','label':'Escalate','object':'Case','recordId':{'type':'Reference','value':'$Record.Id'},
                'inputAssignments':[{'field':'Status','value':{'type':'String','value':'Escalated'}}],'next':None}]}}]}


def test_missing_start_filters_preserve_existing_guard_and_validate():
    original=plan();before=deepcopy(original)
    result=complete_missing_entry_filters(original,'When a Case is created or updated with High Priority and Web Origin, escalate it.')
    config=result['items'][0]['config']
    assert [c['field'] for c in config['startFilters']]==['Priority','Origin']
    assert config['elements']==before['items'][0]['config']['elements']
    assert original==before
    assert result['assumptions']
    ExtendedFlowConfig.model_validate(config)


def test_explicit_every_update_is_never_silently_narrowed():
    original=plan()
    assert complete_missing_entry_filters(original,'Run on every update.')==original


def test_alternative_outcome_work_does_not_get_filtered_away():
    original=plan();original['items'][0]['config']['elements'][0]['defaultNext']='Update'
    assert complete_missing_entry_filters(original,'Create or update Cases.')==original


def test_ticket_repair_uses_completed_filters_as_protected_baseline():
    import json
    from unittest.mock import Mock
    from Backend.AI.app.services.plan_revision_service import RepairProvider
    original=plan();item=original['items'][0];item.update(id='ITEM-ONE',action='CREATE',fullName='Escalate')
    expected=complete_missing_entry_filters(original,'Created or updated Cases.')
    provider=Mock();provider.generate.return_value=json.dumps({'repairs':[{'itemId':'ITEM-ONE','config':expected['items'][0]['config']}]})
    adapter=RepairProvider(provider,{'rejectedPlan':original,'originalRequirement':'Created or updated Cases.', 'failureEvidence':'ITEM-ONE Changed-to-meet-criteria requires update entry filters.'})
    repaired=json.loads(adapter.generate('planning','verified context'))
    assert repaired['items'][0]['config']['startFilters']==expected['items'][0]['config']['startFilters']
    assert original['items'][0]['config']['startFilters']==[]
