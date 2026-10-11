from unittest.mock import Mock,patch
import pytest
from Backend.AI.app.services.discovery_service import (
    simple_object_request, discover_object, request_scope, explicit_objects, referenced_objects, INVENTORY_KINDS,
)
from Backend.AI.app.services.metadata_service import DefaultGenerationRequest,DefaultMetadataPipeline

@pytest.mark.parametrize('text',['Create an object API testing','Create a custom object named API_Testing__c','Create an object named "API Testing"'])
def test_simple_name(text):
    assert simple_object_request(text)['fullName']=='API_Testing__c'

@pytest.mark.parametrize('text',['Create an object named Leave Request with fields and a flow','Create objects One and Two','Create an object and a field','Create a field on Account'])
def test_complex_requests_stay_on_full_discovery(text):
    assert simple_object_request(text) is None


def test_existing_object_responds_without_generating():
    pipeline=Mock();pipeline.cli.return_value={'result':{'records':[{'QualifiedApiName':'API_Testing__c'}],'done':True}}
    with pytest.raises(ValueError,match='already exists'):
        discover_object(pipeline,'org',simple_object_request('Create an object API testing'))
    args=pipeline.cli.call_args.args[0]
    assert '--use-tooling-api' in args and "QualifiedApiName = 'API_Testing__c'" in args[-1]


def test_query_failure_is_not_an_absent_object():
    pipeline=Mock();pipeline.cli.return_value={'result':{'records':[],'done':False}}
    with pytest.raises(ValueError,match='did not complete'):discover_object(pipeline,'org',simple_object_request('Create an object API testing'))


def test_focused_discovery_skips_describes_rules_and_all_inventory(tmp_path):
    pipeline=DefaultMetadataPipeline(tmp_path)
    metadata=Mock();pipeline.metadata_factory=Mock(return_value=metadata)
    with patch.object(pipeline,'version',return_value='65.0'),patch.object(pipeline,'cli',return_value={'result':{'records':[],'done':True}}) as cli:
        _,context=pipeline.discover(DefaultGenerationRequest(requirement='Create an object API testing',target_org='org'))
    assert context['focusedObjectRequest']['fullName']=='API_Testing__c'
    cli.assert_called_once();metadata.find_relevant_objects.assert_not_called();metadata.get_context.assert_not_called()


def test_new_object_layout_options_never_retrieve_org(tmp_path):
    from Backend.AI.app.services.layout_selection_service import LayoutSelectionWorkflow
    from Backend.AI.app.validators.plan_validator import ImplementationPlan
    data={'id':'PLAN-object','requirementId':'r','summary':'Create object','items':[{'id':'obj','action':'CREATE','metadataType':'CustomObject','fullName':'API_Testing__c','config':{},'approval':'PENDING'}]}
    plan=ImplementationPlan.model_validate(data)
    store=Mock();store.get.return_value=plan
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"65.0"}')
    workflow=LayoutSelectionWorkflow(store,tmp_path,'org')
    with patch('Backend.AI.app.services.page_layout_service.PageLayoutService._retrieve',side_effect=AssertionError('unnecessary retrieval')):
        options=workflow.options(plan.id)
    assert options['ready'] and options['objects'][0]['layouts'][0]['created']


def test_new_object_layout_generation_emits_only_new_assignment(tmp_path):
    from Backend.AI.app.validators.metadata_spec_validator import MetadataSpecification
    from Backend.AI.app.services.metadata_generator import SalesforceMetadataGenerator
    from Backend.AI.app.services.page_layout_service import PageLayoutService,Q,layout_path
    import xml.etree.ElementTree as ET
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"65.0"}')
    spec=MetadataSpecification.model_validate({'planId':'PLAN-object','metadata':[{'itemId':'obj','action':'CREATE','metadataType':'CustomObject','fullName':'API_Testing__c','label':'API Testing','config':{}}],'validationIssues':[]})
    SalesforceMetadataGenerator(tmp_path).generate_from_specification(spec)
    with patch.object(PageLayoutService,'_retrieve',side_effect=AssertionError('unnecessary retrieval')):
        report=PageLayoutService(tmp_path,'org').generate(spec)
    assert len(report['layouts'])==1
    assert (tmp_path/layout_path('API_Testing__c-API_Testing Layout')).is_file()
    profile=ET.parse(tmp_path/'force-app/main/default/profiles/Admin.profile-meta.xml').getroot()
    assert [node.findtext(Q('layout')) for node in profile.findall(Q('layoutAssignments'))]==['API_Testing__c-API_Testing Layout']



@pytest.mark.parametrize('requirement,kinds,rules',[
 ('Create a text field on Account',(),False),
 ('Create a validation rule on Account',(),True),
 ('Create a record-triggered Flow on Account',('Flow',),True),
 ('Create an Apex trigger on Account',('ApexClass','ApexTrigger'),True),
 ('Create an LWC to search Contact',('ApexClass','LightningComponentBundle'),True),
 ('Create an object and fields and a Flow',('Flow',),True),
 ('Automate employee onboarding',INVENTORY_KINDS,True),
])
def test_component_families(requirement,kinds,rules):
    scope=request_scope(requirement)
    assert scope['inventoryKinds']==kinds and scope['requiresRules']==rules


def test_complete_names_avoid_incidental_objects():
    catalog=[{'name':'Account'},{'name':'AccountHistory'},{'name':'Contact'},{'name':'ContactHistory'},{'name':'Leave_Request__c'}]
    assert explicit_objects('Create fields on Account and Leave Request',catalog)==['Account','Leave_Request__c']
    assert explicit_objects('Work with Contacts',catalog)==['Contact']


def test_relationship_dependencies_are_explicit_not_all_lookups():
    context={'objects':[{'name':'Account','fields':[
        {'name':'OwnerId','relationshipName':'Owner','referenceTo':['User']},
        {'name':'ParentId','relationshipName':'Parent','referenceTo':['Account']}]}]}
    assert referenced_objects('Use Account.OwnerId',context)=={'User'}
    assert referenced_objects('Create an Account text field',context)==set()


def pipeline_fixture(tmp_path):
    pipeline=DefaultMetadataPipeline(tmp_path)
    metadata=Mock();metadata.list_objects.return_value=[{'name':'Account'},{'name':'AccountHistory'},{'name':'User'}]
    metadata.get_context.side_effect=lambda names:{'objects':[{'name':n,'fields':[
        {'name':'OwnerId','relationshipName':'Owner','referenceTo':['User']}]} for n in names]}
    pipeline.metadata_factory=Mock(return_value=metadata)
    pipeline.rule_discovery=Mock(side_effect=lambda context,*args:{**context,'validationRuleDiscovery':{'status':'complete'}})
    return pipeline,metadata


def test_field_request_reads_only_target_schema_no_inventory_or_rules(tmp_path):
    pipeline,metadata=pipeline_fixture(tmp_path)
    with patch.object(pipeline,'version',return_value='65.0'),patch.object(pipeline,'cli') as cli:
        _,context=pipeline.discover(DefaultGenerationRequest(requirement='Create a text field on Account',target_org='org'))
    metadata.get_context.assert_called_once_with(['Account'])
    metadata.find_relevant_objects.assert_not_called();pipeline.rule_discovery.assert_not_called();cli.assert_not_called()
    assert context['validationRuleDiscovery']['status']=='not-requested'
    assert context['existingComponents']['CustomField']==['Account.OwnerId']


def test_flow_request_only_reads_flow_inventory_and_required_rules(tmp_path):
    pipeline,metadata=pipeline_fixture(tmp_path)
    with patch.object(pipeline,'version',return_value='65.0'),patch.object(pipeline,'cli',return_value={'result':[]}) as cli:
        _,context=pipeline.discover(DefaultGenerationRequest(requirement='Create a record-triggered Flow on Account',target_org='org'))
    cli.assert_called_once();assert cli.call_args.args[0][4]=='Flow'
    pipeline.rule_discovery.assert_called_once()
    assert 'ApexClass' in context['discoveryScope']['uninspectedComponentTypes']


def test_explicit_lookup_adds_related_context(tmp_path):
    pipeline,metadata=pipeline_fixture(tmp_path)
    with patch.object(pipeline,'version',return_value='65.0'),patch.object(pipeline,'cli'):
        _,context=pipeline.discover(DefaultGenerationRequest(requirement='Create a formula field using Account.OwnerId',target_org='org'))
    assert [obj['name'] for obj in context['objects']]==['Account','User']


def test_inventory_error_does_not_become_empty_scope(tmp_path):
    pipeline,metadata=pipeline_fixture(tmp_path)
    with patch.object(pipeline,'version',return_value='65.0'),patch.object(pipeline,'cli',return_value={'result':None}):
        with pytest.raises(ValueError,match='discovery response'):
            pipeline.discover(DefaultGenerationRequest(requirement='Create a Flow on Account',target_org='org'))
