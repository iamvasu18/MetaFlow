import base64
import io
import zipfile
import xml.etree.ElementTree as ET
import httpx
import pytest
from Backend.AI.app.tests.test_salesforce_api_discovery import connection
from Backend.AI.app.services.salesforce_metadata_api import (
    SalesforceMetadataApi,metadata_archive,import_layout_archive,NS,SOAP,Q,
)

PREFIX='force-app/main/default/'
JOB='0Af000000000001AAA'
def reply(method,result):
    return httpx.Response(200,text=f'<s:Envelope xmlns:s="{SOAP}" xmlns:m="{NS}"><s:Body><m:{method}Response>{result}</m:{method}Response></s:Body></s:Envelope>')

def client(connection,handler):
    connection(handler)  # Fixture supplies owned encrypted credentials.
    return SalesforceMetadataApi('u','org','67.0',httpx.Client(transport=httpx.MockTransport(handler)))

def test_archive_is_narrow_and_merges_decomposed_fields():
    files={
        PREFIX+'objects/Test__c/Test__c.object-meta.xml':f'<CustomObject xmlns="{NS}"><label>Test</label><pluralLabel>Tests</pluralLabel></CustomObject>',
        PREFIX+'objects/Test__c/fields/Status__c.field-meta.xml':f'<CustomField xmlns="{NS}"><fullName>Status__c</fullName><type>Text</type><length>20</length></CustomField>',
        PREFIX+'flows/TestFlow.flow-meta.xml':f'<Flow xmlns="{NS}"><label>Test</label><status>Draft</status></Flow>',
        PREFIX+'classes/TestController.cls':'public with sharing class TestController {}',
        PREFIX+'classes/TestController.cls-meta.xml':f'<ApexClass xmlns="{NS}"><apiVersion>67.0</apiVersion><status>Active</status></ApexClass>',
        PREFIX+'lwc/testSearch/testSearch.js':'export default class TestSearch {}',
    }
    with zipfile.ZipFile(io.BytesIO(metadata_archive(files,'67.0'))) as archive:
        assert 'objects/Test__c.object' in archive.namelist()
        assert 'flows/TestFlow.flow' in archive.namelist()
        assert 'classes/TestController.cls-meta.xml' in archive.namelist()
        root=ET.fromstring(archive.read('objects/Test__c.object'))
        assert root.findtext(Q('fields')+'/'+Q('fullName'))=='Status__c'
        manifest=ET.fromstring(archive.read('package.xml'))
        assert not any(n.text=='*' for n in manifest.iter())

@pytest.mark.parametrize('path',['force-app/main/default/../secret','force-app/main/default/reports/Report.report-meta.xml','force-app/main/default/objects/A__c/unknown/Name.xml'])
def test_archive_rejects_unsafe_or_unsupported_sources(path):
    with pytest.raises(ValueError):metadata_archive({path:'<xml />'},'67.0')

def test_submit_is_async_and_check_only(connection):
    calls=[]
    def handler(request):
        calls.append(request)
        root=ET.fromstring(request.content)
        assert root.findtext('.//'+Q('checkOnly'))=='true'
        assert root.findtext('.//'+Q('rollbackOnError'))=='true'
        assert root.findtext('.//'+Q('testLevel'))=='RunSpecifiedTests'
        assert root.findtext('.//'+Q('runTests'))=='ControllerTest'
        return reply('deploy',f'<m:result><m:id>{JOB}</m:id><m:done>false</m:done></m:result>')
    result=client(connection,handler).deploy({'files':{PREFIX+'classes/ControllerTest.cls':'@isTest class ControllerTest {}'},'apiVersion':'67.0','testClasses':['ControllerTest']})
    assert result['result']['id']==JOB and result['result']['done'] is False
    assert len(calls)==1

def test_mutation_timeout_is_not_retried(connection):
    calls=[]
    def handler(request):
        calls.append(request);raise httpx.ReadTimeout('timeout')
    with pytest.raises(RuntimeError,match='No operation was retried'):
        client(connection,handler).deploy({'files':{},'apiVersion':'67.0'})
    assert len(calls)==1

def test_status_normalizes_errors_and_tests(connection):
    result=f'<m:result><m:id>{JOB}</m:id><m:done>true</m:done><m:success>false</m:success><m:details><m:componentFailures><m:fullName>Test</m:fullName><m:problem>Invalid source</m:problem></m:componentFailures><m:runTestResult><m:numTestsRun>2</m:numTestsRun><m:numFailures>0</m:numFailures></m:runTestResult></m:details></m:result>'
    value=client(connection,lambda request:reply('checkDeployStatus',result)).report(JOB)
    assert value['status']==1
    assert value['result']['details']['componentFailures'][0]['problem']=='Invalid source'
    assert value['result']['details']['runTestResult']['numTestsRun']==2

def test_status_wrong_job_is_rejected(connection):
    response='<m:result><m:id>0Af000000000002AAA</m:id><m:done>false</m:done></m:result>'
    with pytest.raises(RuntimeError):client(connection,lambda request:reply('checkDeployStatus',response)).report(JOB)

def test_inventory_at_limit_is_not_assumed_complete(connection):
    records=''.join(f'<m:result><m:fullName>Layout{i}</m:fullName></m:result>' for i in range(1000))
    with pytest.raises(ValueError,match='1,000'):client(connection,lambda request:reply('listMetadata',records)).list_metadata('Layout')

def test_retrieve_import_only_expected_layout_and_profile(tmp_path):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr('unpackaged/profiles/Admin.profile',f'<Profile xmlns="{NS}"/>')
        archive.writestr('unpackaged/layouts/Account-Account Layout.layout',f'<Layout xmlns="{NS}"/>')
        archive.writestr('../../secret.txt','not extracted')
        archive.writestr('unpackaged/classes/Unrelated.cls','not extracted')
    import_layout_archive(base64.b64encode(stream.getvalue()).decode(),{'Layout':['Account-Account Layout']},tmp_path)
    assert len(list(tmp_path.rglob('*.*')))==2
    assert (tmp_path/PREFIX/'profiles/Admin.profile-meta.xml').exists()

def test_missing_requested_layout_fails(tmp_path):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:archive.writestr('profiles/Admin.profile',f'<Profile xmlns="{NS}"/>')
    with pytest.raises(RuntimeError,match='all requested'):
        import_layout_archive(base64.b64encode(stream.getvalue()).decode(),{'Layout':['Account-Account Layout']},tmp_path)

def test_authenticated_pipeline_submits_and_reports_without_cli(connection,monkeypatch):
    from Backend.AI.app.tests.test_workspace_regression import package,accounts
    from Backend.AI.app.services.metadata_service import DefaultMetadataPipeline
    import Backend.AI.app.services.salesforce_api_client as transport
    import Backend.AI.app.services.salesforce_metadata_api as metadata_transport
    requests=[]
    def handler(request):
        requests.append(request)
        if request.method=='GET':
            if request.url.path.endswith('/sobjects'):return httpx.Response(200,json={'sobjects':[{'name':'Metaflow__c','label':'Metaflow'}]})
            return httpx.Response(200,json={'name':'Metaflow__c','fields':[]})
        if request.headers['SOAPAction']=='deploy':return reply('deploy',f'<m:result><m:id>{JOB}</m:id></m:result>')
        return reply('checkDeployStatus',f'<m:result><m:id>{JOB}</m:id><m:done>true</m:done><m:success>true</m:success><m:status>Succeeded</m:status></m:result>')
    connection(handler)
    monkeypatch.setattr(transport,'http_pool',lambda:httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(metadata_transport,'http_pool',transport.http_pool)
    pipeline=DefaultMetadataPipeline()
    def fail_cli(*args):raise AssertionError('CLI must not run in authenticated deployment')
    monkeypatch.setattr(pipeline,'cli',fail_cli)
    _,bundle=package(state='generated');bundle['targetOrg']='org'
    path=next(iter(bundle['files']))
    bundle['files'][path]=f'<CustomField xmlns="{NS}"><fullName>UI_Description__c</fullName><type>Text</type><label>UI Description</label><length>80</length></CustomField>'
    bundle['baseFiles']=dict(bundle['files']);bundle['sourceHash']=pipeline.fingerprint(bundle);bundle['approvedHash']=bundle['sourceHash']
    token=accounts.current_account.set('u')
    try:
        result=pipeline.deploy(bundle)
        assert result['result']['done'] is False
        bundle['jobId']=result['result']['id']
        assert pipeline.report(bundle)['result']['success'] is True
    finally:accounts.current_account.reset(token)
    assert any(r.headers.get('SOAPAction')=='deploy' for r in requests)

def test_layout_retrieval_uses_api_and_writes_dx_sources(connection,tmp_path,monkeypatch):
    from Backend.AI.app.services.page_layout_service import PageLayoutService
    import Backend.AI.app.services.salesforce_metadata_api as module
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr('unpackaged/profiles/Admin.profile',f'<Profile xmlns="{NS}"/>')
        archive.writestr('unpackaged/layouts/Account-Account Layout.layout',f'<Layout xmlns="{NS}"/>')
    encoded=base64.b64encode(stream.getvalue()).decode()
    job='09S000000000001AAA'
    def handler(request):
        method=request.headers['SOAPAction']
        if method=='listMetadata':
            kind=ET.fromstring(request.content).findtext('.//'+Q('type'))
            return reply(method,'<m:result><m:fullName>Account-Account Layout</m:fullName></m:result>' if kind=='Layout' else '')
        if method=='retrieve':return reply(method,f'<m:result><m:id>{job}</m:id></m:result>')
        return reply(method,f'<m:result><m:id>{job}</m:id><m:done>true</m:done><m:success>true</m:success><m:zipFile>{encoded}</m:zipFile></m:result>')
    api=client(connection,handler)
    monkeypatch.setattr(module,'owned_metadata_api',lambda *args:api)
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    service=PageLayoutService(tmp_path,'org')
    monkeypatch.setattr(service,'_cli',lambda *args:pytest.fail('Layout CLI called'))
    profile,names=service._retrieve(tmp_path,objects={'Account'})
    assert profile.tag==Q('Profile') and names=={'Account-Account Layout'}

def test_soap_fault_redacts_credentials(connection):
    def handler(request):
        return httpx.Response(500,text=f'<s:Envelope xmlns:s="{SOAP}"><s:Body><s:Fault><faultcode>sf:ERROR</faultcode><faultstring>secret-access secret-refresh</faultstring></s:Fault></s:Body></s:Envelope>')
    with pytest.raises(RuntimeError) as error:client(connection,handler).list_metadata('Layout')
    assert 'secret-access' not in str(error.value) and 'secret-refresh' not in str(error.value)
