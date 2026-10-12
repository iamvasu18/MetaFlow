from copy import deepcopy
from types import SimpleNamespace
import xml.etree.ElementTree as ET
import pytest
from Backend.AI.app.services.permission_set_service import *
from Backend.AI.app.services.metadata_service import MetadataService
from Backend.AI.app.services.salesforce_metadata_api import metadata_archive
from Backend.AI.app.validators.plan_validator import ImplementationPlan, validate_plan
CONFIG={'objectPermissions':[{'object':'Account','allowRead':True,'allowEdit':True}], 'fieldPermissions':[{'field':'Account.Phone','readable':True,'editable':True}], 'classAccesses':[{'apexClass':'AccountService','enabled':True}], 'userPermissions':[{'name':'APIEnabled','enabled':True}]}
def plan():return {'id':'PLAN-ps','requirementId':'r','summary':'Create limited access','status':'APPROVED','items':[{'id':'ps','action':'CREATE','metadataType':'PermissionSet','fullName':'Account_Access','label':'Account Access','approval':'APPROVED','config':deepcopy(CONFIG)}]}
class Api:
    def describe_object(self,name):
        if name=='PermissionSet':return {'name':name,'fields':[{'name':'PermissionsAPIEnabled','type':'boolean'}]}
        return {'name':name,'fields':[{'name':'Phone','type':'phone','permissionable':True}]}
    def list_components(self,kind):return [{'fullName':'AccountService'}]
def test_generator_plan_archive_and_spec(tmp_path):
    assert validate_plan(plan()).valid
    item=ImplementationPlan.model_validate(plan()).items[0];path=generate_permission_set(item,tmp_path)
    label,config=source_config(path.read_text());assert label=='Account Access'
    assert config.objectPermissions[0].allowDelete is False
    assert config.objectPermissions[0].modifyAllRecords is False
    assert metadata_archive({path.relative_to(tmp_path).as_posix():path.read_text()},'67.0')
    class Provider:
        def generate(self,**kw):pytest.fail('No second AI call')
    assert MetadataService(Provider()).generate_specification(ImplementationPlan.model_validate(plan())).metadata[0].metadataType=='PermissionSet'
@pytest.mark.parametrize('config',[
 {'objectPermissions':[{'object':'Account','allowEdit':True}]},
 {'fieldPermissions':[{'field':'Account.Phone','editable':True}]},
 {'fieldPermissions':[{'field':'Account.Phone','readable':True}]},
 {'objectPermissions':[{'object':'Account','allowRead':'true'}]},
 {'objectPermissions':[{'object':'Account'},{'object':'Account'}]},
 {'unexpectedAdminAccess':True}])
def test_invalid_grants(config):
    with pytest.raises(ValueError):PermissionSetConfig.model_validate(config)
def test_org_reference_checks():
    assert preflight_permission_set('Account_Access','Account Access',CONFIG,Api())
    bad=deepcopy(CONFIG);bad['fieldPermissions'][0]['field']='Account.Missing__c'
    with pytest.raises(ValueError,match='Unknown field'):preflight_permission_set('Account_Access','Account Access',bad,Api())
    bad=deepcopy(CONFIG);bad['userPermissions'][0]['name']='InventedPermission'
    with pytest.raises(ValueError,match='not exposed'):preflight_permission_set('Account_Access','Account Access',bad,Api())
def test_dependency_required():
    data=plan();data['items'].append({'id':'field','action':'CREATE','metadataType':'CustomField','fullName':'Account.Phone','config':{'fieldType':'Phone'}})
    with pytest.raises(ValueError,match='dependency'):preflight_permission_set('Account_Access','Account Access',CONFIG,Api(),data)
def fixture(tmp_path):
    text=generate_permission_set(ImplementationPlan.model_validate(plan()).items[0],tmp_path).read_text()
    package={'state':'deployed','operation':'deploy','components':[{'metadataType':'PermissionSet','fullName':'Account_Access'}], 'files':{component_path('PermissionSet','Account_Access').as_posix():text}, 'lastResult':{'result':{'success':True,'done':True,'checkOnly':False,'details':{'componentSuccesses':[{'componentType':'PermissionSet','fullName':'Account_Access','success':True,'id':'0PS000000000001AAA'}]}}}}
    class AssignmentApi:
        owner='owner';org='org';base='/services/data/v67.0';http=None
        def query(self,sql):return {'records':[{'Id':'005000000000001AAA','Username':'user@example.com','IsActive':True}]} if ' FROM User ' in sql else {'records':[]}
    class Transport:
        api=AssignmentApi()
        def call(self,*a,**kw):
            node=ET.Element('{'+NS+'}result');record=ET.fromstring(text);record.tag='{'+NS+'}records';ET.SubElement(record,'{'+NS+'}fullName').text='Account_Access';node.append(record);return [node]
    return package,Transport()
def test_assignment_confirmation_and_real_deploy(tmp_path):
    package,transport=fixture(tmp_path);service=PermissionAssignmentService(transport)
    with pytest.raises(ValueError,match='confirmation'):service.assign(package,'Account_Access','user@example.com',False,lambda p:None)
    package['lastResult']['result']['checkOnly']=True
    with pytest.raises(ValueError,match='real deployment'):service.assign(package,'Account_Access','user@example.com',True,lambda p:None)
def test_assignment_timeout_is_not_retried(tmp_path,monkeypatch):
    from Backend.AI.app.services import salesforce_api_client as clients
    import httpx
    package,transport=fixture(tmp_path);calls=[]
    class Http:
        def post(self,*a,**kw):calls.append(kw);raise httpx.ReadTimeout('lost response')
    transport.api.http=Http();monkeypatch.setattr(clients,'load_org_tokens',lambda *a:{'instance_url':'https://example.salesforce.com','access_token':'test'})
    service=PermissionAssignmentService(transport)
    with pytest.raises(ValueError,match='unconfirmed'):service.assign(package,'Account_Access','user@example.com',True,lambda p:None)
    with pytest.raises(ValueError,match='previous assignment'):service.assign(package,'Account_Access','user@example.com',True,lambda p:None)
    assert len(calls)==1
    assert calls[0]['json']=={'PermissionSetId':'0PS000000000001AAA','AssigneeId':'005000000000001AAA'}

def test_pipeline_generates_one_permission_file_and_preserves_access_intent(tmp_path,monkeypatch):
    from Backend.AI.app.services.metadata_service import DefaultMetadataPipeline,DefaultGenerationRequest
    import json
    import pathlib
    pipeline=DefaultMetadataPipeline(project_root=pathlib.Path.cwd())
    context={'objects':[{'name':'Account','label':'Account','fields':[{'name':'Phone','type':'phone','label':'Phone','permissionable':True}]}], 'objectCatalog':[{'name':'Account','label':'Account'}], 'existingComponents':{'PermissionSet':[],'ApexClass':['AccountService']},'validationRuleDiscovery':{'status':'not-requested'}}
    metadata=SimpleNamespace(api=Api())
    monkeypatch.setattr(pipeline,'discover',lambda request:(metadata,deepcopy(context)))
    import Backend.AI.app.services.metadata_service as service_module
    monkeypatch.setattr(service_module,'connected_api',lambda metadata:metadata.api)
    data=plan();data['status']='DRAFT';data['items'][0]['approval']='PENDING'
    class Provider:
        calls=0
        def generate(self,**kw):self.calls+=1;return json.dumps(data)
    provider=Provider()
    bundle=pipeline.generate(DefaultGenerationRequest(requirement='Create a Permission Set named Account Access with Account read/edit, Phone read/edit, AccountService class access and API access',target_org='app_ours'),provider)
    assert provider.calls==1
    assert list(bundle['files'])==['force-app/main/default/permissionsets/Account_Access.permissionset-meta.xml']
    assert bundle['components']==[{'metadataType':'PermissionSet','fullName':'Account_Access'}]
    assert bundle['state']=='generated'


def test_assignment_success_is_single_explicit_post(tmp_path,monkeypatch):
    from Backend.AI.app.services import salesforce_api_client as clients
    package,transport=fixture(tmp_path);calls=[]
    class Http:
        def post(self,*a,**kw):
            calls.append(kw)
            return SimpleNamespace(status_code=201,json=lambda:{'success':True,'id':'0Pa000000000001AAA'})
    transport.api.http=Http();monkeypatch.setattr(clients,'load_org_tokens',lambda *a:{'instance_url':'https://example.salesforce.com','access_token':'test'})
    result=PermissionAssignmentService(transport).assign(package,'Account_Access','user@example.com',True,lambda p:None)
    assert result['state']=='assigned' and len(calls)==1

def test_live_permission_drift_blocks_assignment(tmp_path):
    package,transport=fixture(tmp_path)
    original=transport.call
    def changed(*a,**kw):
        nodes=original(*a,**kw)
        record=nodes[0].find('{'+NS+'}records')
        record.find('{'+NS+'}objectPermissions/{'+NS+'}allowDelete').text='true'
        return nodes
    transport.call=changed
    with pytest.raises(ValueError,match='differ'):PermissionAssignmentService(transport).assign(package,'Account_Access','user@example.com',True,lambda p:None)

def test_permission_source_edit_revalidates_and_clears_prior_approval(tmp_path):
    from Backend.AI.app.services.component_source_service import apply_source_changes
    item=ImplementationPlan.model_validate(plan()).items[0];path=generate_permission_set(item,tmp_path)
    relative=path.relative_to(tmp_path).as_posix();source=path.read_text()
    package={'components':[{'metadataType':'PermissionSet','fullName':'Account_Access'}], 'files':{relative:source},'sourceHash':'old','state':'validated','approvedHash':'old','validatedHash':'old','lastResult':{'old':True}}
    updated=apply_source_changes(package,'Account_Access',{relative:source.replace('<editable>true</editable>','<editable>false</editable>')},'old',lambda p:'new')
    assert updated['state']=='generated' and updated['approvedHash'] is None and updated['validatedHash'] is None
    assert 'lastResult' not in updated
    assert package['files'][relative]==source
