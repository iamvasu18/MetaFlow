import pytest
from Backend.AI.app.services.discovery_service import (
    check_object_dependencies, MissingObjectDependency, check_requested_components,
)
from Backend.AI.app.services.planning_clarification import planning_error_detail

@pytest.mark.parametrize('text',[
    'Create a flow on Absent__c object',
    'Create a field named Status on Absent__c',
    'Create an Apex trigger for object Absent__c',
    'Create a Lightning web component for Absent__c object',
    'Create a validation rule on Absent__c object',
    'Create a lookup to Absent__c',
])
def test_missing_parent_asks_before_generation(text):
    with pytest.raises(MissingObjectDependency) as error:check_object_dependencies(text,[])
    detail=planning_error_detail(error.value)
    assert detail['code']=='CLARIFICATION_REQUIRED'
    assert 'Absent__c' in detail['question'] and 'accessible' in detail['question']

def test_existing_parent_needs_no_question():
    check_object_dependencies('Create a flow on Account object',[{'name':'Account','label':'Account'}])

def test_explicit_object_creation_satisfies_dependency():
    check_object_dependencies('Create a custom object named Leave_Request__c and a flow on Leave_Request__c object',[])

def test_chat_answer_authorizes_parent_creation():
    check_object_dependencies('Create a flow on Leave__c object\n\nClarification question: Missing object\nUser answer: Create a custom object named Leave__c with a Date field',[])

def test_chat_answer_can_replace_missing_parent():
    check_object_dependencies("Create a flow on Missing__c object\n\nClarification question: I couldn't find Missing__c in the connected org\nUser answer: Use Account instead",[{'name':'Account','label':'Account'}])

def test_replacement_must_be_verified():
    with pytest.raises(MissingObjectDependency):
        check_object_dependencies("Create a flow on Missing__c object\n\nClarification question: I couldn't find Missing__c in the connected org\nUser answer: Use Another__c instead",[])

def test_denied_creation_does_not_satisfy_dependency():
    with pytest.raises(MissingObjectDependency):
        check_object_dependencies('Do not create object Missing__c. Create a flow on Missing__c object',[])
    with pytest.raises(MissingObjectDependency):
        check_object_dependencies('Do not create a custom object named Missing__c. Create a flow on Missing__c object',[])

def test_reuse_with_field_followup_is_not_no_change():
    context={'objectCatalog':[{'name':'Account','label':'Account'}]}
    check_requested_components('Create an object named Account\nUser answer: Use the existing Account and add a Status field',context)

def test_reused_parent_does_not_reask_during_plan_check():
    from Backend.AI.app.services.discovery_service import check_planned_components
    context={'objectCatalog':[{'name':'Account','label':'Account'}]}
    check_planned_components({'items':[
        {'metadataType':'CustomObject','fullName':'Account','action':'NO_CHANGE'},
        {'metadataType':'CustomField','fullName':'Account.Status__c','action':'CREATE'},
    ]},'Create an object named Account\nUser answer: Use Account and add a Status field',context)

@pytest.mark.parametrize('error',[
    'Flow requires existing org metadata for Leave__c.',
    'Field parent Leave__c is neither verified in the org nor created in this plan.',
    'Flow references unknown field Leave__c.Status__c.',
])
def test_dependency_validation_errors_become_chat_questions(error):
    detail=planning_error_detail(ValueError(error))
    assert detail['code']=='CLARIFICATION_REQUIRED' and 'Leave__c' in detail['question']
