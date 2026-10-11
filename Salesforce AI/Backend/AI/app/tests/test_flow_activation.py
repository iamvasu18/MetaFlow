from copy import deepcopy
import httpx
import pytest
from Backend.AI.app.tests.test_salesforce_api_discovery import connection
from Backend.AI.app.tests.test_workspace_regression import client
from Backend.AI.app.services.flow_activation_service import FlowActivationService
from Backend.AI.app.services.salesforce_metadata_api import metadata_archive,NS

VERSION='301000000000001AAA';DEFINITION='300000000000001AAA'
def bundle():
    return {'state':'deployed','operation':'deploy','components':[{'metadataType':'Flow','fullName':'TestFlow'}],
        'lastResult':{'result':{'done':True,'success':True,'checkOnly':False,'completedDate':'2026-10-11T00:00:00Z',
        'details':{'componentSuccesses':[{'componentType':'Flow','fullName':'TestFlow','id':VERSION,'success':True}]}}}}

def service(connection,mode='success'):
    calls=[];active=[False]
    def handler(request):
        calls.append(request)
        if request.method=='PATCH':
            assert request.url.path.endswith('/tooling/sobjects/FlowDefinition/'+DEFINITION)
            assert b'"activeVersionNumber":1' in request.content
            if mode=='timeout':raise httpx.ReadTimeout('timeout')
            if mode=='reject':return httpx.Response(400,json=[{'message':'The Flow has activation errors.'}])
            active[0]=True;return httpx.Response(204)
        query=request.url.params['q']
        if 'FROM FlowDefinition' in query:
            rows=[{'Id':DEFINITION,'DeveloperName':'TestFlow','NamespacePrefix':None,'ActiveVersionId':VERSION if active[0] else None,'LatestVersionId':'301000000000002AAA' if mode=='newer' else VERSION}]
        else:
            rows=[{'Id':VERSION,'DefinitionId':DEFINITION,'VersionNumber':1,'Status':'Active' if active[0] else 'Draft','LastModifiedDate':'2026-10-12T00:00:00Z' if mode=='edited' else '2026-10-10T23:59:00Z'}]
        return httpx.Response(200,json={'records':rows,'done':True})
    connection(handler)
    return FlowActivationService('u','org','67.0',httpx.Client(transport=httpx.MockTransport(handler))),calls,active

def test_activate_exact_deployed_version_and_verify(connection):
    api,calls,_=service(connection);package=bundle();saved=[]
    api.activate(package,'TestFlow',lambda value:saved.append(deepcopy(value)))
    assert [s['flowActivations']['TestFlow']['state'] for s in saved]==['running','active']
    assert sum(r.method=='PATCH' for r in calls)==1
    api.activate(package,'TestFlow',lambda value:None)
    assert sum(r.method=='PATCH' for r in calls)==1

@pytest.mark.parametrize('mode',['newer','edited'])
def test_drift_blocks_activation(connection,mode):
    api,calls,_=service(connection,mode)
    with pytest.raises(ValueError):api.activate(bundle(),'TestFlow',lambda value:None)
    assert not any(r.method=='PATCH' for r in calls)

def test_activation_timeout_not_resubmitted(connection):
    api,calls,_=service(connection,'timeout');package=bundle()
    api.activate(package,'TestFlow',lambda value:None)
    assert package['flowActivations']['TestFlow']['state']=='unknown'
    api.activate(package,'TestFlow',lambda value:None)
    assert sum(r.method=='PATCH' for r in calls)==1

def test_salesforce_activation_error_is_displayed(connection):
    api,_,_=service(connection,'reject');package=bundle()
    api.activate(package,'TestFlow',lambda value:None)
    assert package['flowActivations']['TestFlow']['state']=='failed'
    assert 'activation errors' in package['flowActivations']['TestFlow']['message']

@pytest.mark.parametrize('state',['generated','validated','pending','unknown','failed'])
def test_only_deployed_flows_can_activate(connection,state):
    api,calls,_=service(connection);package=bundle();package['state']=state
    with pytest.raises(ValueError):api.activate(package,'TestFlow',lambda value:None)
    assert not calls

def test_version_id_must_come_from_deployment_report(connection):
    api,calls,_=service(connection);package=bundle()
    package['lastResult']['result']['details']['componentSuccesses'][0]['id']=DEFINITION
    with pytest.raises(ValueError,match='will not guess'):api.activate(package,'TestFlow',lambda value:None)
    assert not calls

def test_activation_recovery_confirms_effect_without_repeating(connection):
    api,calls,active=service(connection);package=bundle();package['flowActivations']={'TestFlow':{'state':'running'}};active[0]=True
    api.activate(package,'TestFlow',lambda value:None)
    assert package['flowActivations']['TestFlow']['state']=='active' and not any(r.method=='PATCH' for r in calls)

def test_active_source_cannot_bypass_separate_action():
    with pytest.raises(ValueError,match='use Activate'):
        metadata_archive({'force-app/main/default/flows/TestFlow.flow-meta.xml':f'<Flow xmlns="{NS}"><status>Active</status></Flow>'},'67.0')

def test_activation_route_rejects_unowned_plan(client):
    assert client.post('/api/plans/PLAN-not-ours/activate-flow',json={'component_name':'TestFlow','source_hash':'a'*64}).status_code==404

def test_activation_route_requires_exact_approved_hash(client):
    assert client.post('/api/plans/PLAN-old/activate-flow',json={'component_name':'TestFlow','source_hash':'a'*64}).status_code==409
