import pytest
from Backend.AI.app.services.apex_callout_policy import check_callout_source

SOURCE="public with sharing class Integration { public static void run() { HttpRequest req=new HttpRequest(); req.setEndpoint('callout:Billing/accounts'); req.setTimeout(10000); HttpResponse response=new Http().send(req); } }"


def test_verified_named_credential_literal_is_allowed():
    assert check_callout_source(SOURCE,{'namedCredentials':['Billing']},'Service')


@pytest.mark.parametrize('source,context',[
    (SOURCE,{}),
    (SOURCE.replace('callout:Billing/accounts','https://example.com/accounts'),{'namedCredentials':['Billing']}),
    (SOURCE.replace("'callout:Billing/accounts'",'endpoint'),{'namedCredentials':['Billing']}),
    (SOURCE.replace('req.setTimeout(10000);',''),{'namedCredentials':['Billing']}),
    (SOURCE.replace('10000','120001'),{'namedCredentials':['Billing']}),
])
def test_unverified_dynamic_raw_or_unbounded_callouts_are_rejected(source,context):
    with pytest.raises(ValueError):check_callout_source(source,context,'Service')


def test_queueable_requires_allows_callouts():
    with pytest.raises(ValueError,match='AllowsCallouts'):
        check_callout_source(SOURCE,{'namedCredentials':['Billing']},'Queueable')


def test_http_send_inside_record_loop_is_rejected():
    source=SOURCE.replace('HttpResponse response=new Http().send(req);','for(Integer i=0;i<200;i++) { HttpResponse response=new Http().send(req); }')
    with pytest.raises(ValueError,match='inside loops'):
        check_callout_source(source,{'namedCredentials':['Billing']},'Service')


def test_discovery_selects_only_explicit_verified_named_credential(monkeypatch):
    from unittest.mock import Mock
    from Backend.AI.app.services import salesforce_metadata_api
    from Backend.AI.app.services.apex_callout_policy import discover_callout_context
    transport=Mock();transport.list_metadata.return_value=[{'fullName':'Billing'},{'fullName':'Other'}]
    monkeypatch.setattr(salesforce_metadata_api,'owned_metadata_api',lambda *args:transport)
    original={'objects':[]}
    result=discover_callout_context(original,'org','67.0','Create Apex HTTP callout using Named Credential Billing.')
    assert result['namedCredentials']==['Billing'] and 'namedCredentials' not in original
    with pytest.raises(ValueError,match='cannot be safely guessed'):
        discover_callout_context(original,'org','67.0','Create an HTTP callout to an external API.')


def test_apex_package_accepts_named_credential_with_real_mock_contract(tmp_path):
    from Backend.AI.app.services.apex_service import ApexAutomationService,ApexSources,ApexRequest
    source=SOURCE.replace('static void run()', 'static Integer run()').replace('HttpResponse response=new Http().send(req);','HttpResponse response=new Http().send(req); return response.getStatusCode();')
    tests='''@IsTest private class IntegrationTest {
        private class FakeResponse implements HttpCalloutMock {
            public HttpResponse respond(HttpRequest request) { HttpResponse result=new HttpResponse(); result.setStatusCode(200); return result; }
        }
        @IsTest static void successfulResponse() {
            Test.setMock(HttpCalloutMock.class,new FakeResponse());
            Test.startTest(); Integer status=Integration.run(); Test.stopTest();
            Assert.areEqual(200,status);
        }
    }'''
    package=ApexSources(classes=[{'name':'Integration','apex_kind':'Service','body':source},
        {'name':'IntegrationTest','apex_kind':'Test','body':tests}],triggers=[])
    names,components,_=ApexAutomationService(project_root=tmp_path).check_sources(ApexRequest(class_name='Integration',requirement='Return external status using Named Credential Billing.',target_org='AIOrg'),package,{'objects':[],'namedCredentials':['Billing']})
    assert names==['IntegrationTest']
    assert len(components)==2
