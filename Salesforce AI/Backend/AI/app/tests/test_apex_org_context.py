from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock
import json
import pytest
from Backend.AI.app.services.apex_org_context import ApexOrgContext
from Backend.AI.app.services.apex_service import ApexAutomationService, ApexRequest
from Backend.AI.app.tests.test_apex_enhanced import SOURCE

CONTEXT={'objects':[{'name':'Account','fields':[{'name':'Name'},{'name':'Terms_Agreements__c'}]}]}
RULE='''<ValidationRule xmlns="http://soap.sforce.com/2006/04/metadata"><active>{active}</active><errorConditionFormula>NOT(Terms_Agreements__c)</errorConditionFormula><errorMessage>Please accept Terms &amp; Agreements.</errorMessage><errorDisplayField>Terms_Agreements__c</errorDisplayField></ValidationRule>'''

def transport(active='true',missing=False,pending=False):
    calls=[]
    def cli(args,cwd=None):
        calls.append((args,cwd))
        if args[:3]==['org','list','metadata']:
            return {'result':[{'fullName':'Account.AcceptTerms'},{'fullName':'Contact.OtherRule'}]}
        if not missing:
            path=Path(cwd)/'force-app/main/default/objects/Account/validationRules/AcceptTerms.validationRule-meta.xml'
            path.parent.mkdir(parents=True);path.write_text(RULE.format(active=active),encoding='utf-8')
        return {'result':{'done':not pending,'success':not pending}}
    return cli,calls

def test_active_rule_formula_and_message_discovered_without_org_mutation():
    cli,calls=transport();original=deepcopy(CONTEXT)
    result=ApexOrgContext(cli).enrich(CONTEXT,'AIOrg','67.0')
    assert CONTEXT==original
    rule=result['objects'][0]['validationRules'][0]
    assert rule['errorConditionFormula']=='NOT(Terms_Agreements__c)'
    assert rule['errorMessage']=='Please accept Terms & Agreements.'
    assert rule['errorDisplayField']=='Terms_Agreements__c'
    assert result['validationRuleDiscovery']['activeRuleCount']==1
    args=calls[1][0]
    assert 'ValidationRule:Account.AcceptTerms' in args
    assert 'ValidationRule:Contact.OtherRule' not in args
    assert args[:3]==['project','retrieve','start']
    assert not Path(calls[1][1]).exists()

def test_inactive_rules_are_not_generation_constraints():
    cli,_=transport(active='false')
    result=ApexOrgContext(cli).enrich(CONTEXT,'AIOrg','67.0')
    assert result['objects'][0]['validationRules']==[]

@pytest.mark.parametrize('kwargs',[{'missing':True},{'pending':True},{'active':'unknown'}])
def test_incomplete_or_invalid_discovery_fails_closed(kwargs):
    cli,_=transport(**kwargs)
    with pytest.raises(RuntimeError):ApexOrgContext(cli).enrich(CONTEXT,'AIOrg','67.0')

def test_no_rules_is_verified_without_retrieval():
    cli=Mock(return_value={'result':[]})
    result=ApexOrgContext(cli).enrich(CONTEXT,'AIOrg','67.0')
    assert result['validationRuleDiscovery']['status']=='complete'
    assert cli.call_count==1

def test_transport_error_does_not_become_empty_rules():
    with pytest.raises(RuntimeError):ApexOrgContext(Mock(side_effect=RuntimeError('Denied'))).enrich(CONTEXT,'AIOrg','67.0')

def test_single_listing_record_is_supported():
    cli,_=transport()
    def single(args,cwd=None):
        result=cli(args,cwd)
        if args[:3]==['org','list','metadata']:result['result']={'fullName':'Account.AcceptTerms'}
        return result
    assert ApexOrgContext(single).enrich(CONTEXT,'AIOrg','67.0')['validationRuleDiscovery']['activeRuleCount']==1

def test_generator_receives_fresh_rule_context(tmp_path):
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    metadata=Mock();metadata.get_context.return_value=CONTEXT
    service=ApexAutomationService(tmp_path,metadata_factory=lambda org:metadata)
    cli,calls=transport();service.cli=cli
    provider=Mock();provider.generate.return_value=json.dumps(SOURCE)
    request=ApexRequest(class_name='ContactSearchService',requirement='Test',objects=['Account'])
    bundle=service.generate(request,provider)
    sent=json.loads(provider.generate.call_args.kwargs['user_prompt'])
    assert sent['verifiedContext']['objects'][0]['validationRules'][0]['fullName']=='Account.AcceptTerms'
    assert bundle['validationRuleDiscovery']['status']=='complete'
    service.generate(request,provider)
    assert len(calls)==4  # Fresh listing/retrieval on both generations.

def test_generation_stops_before_provider_when_rule_discovery_fails(tmp_path):
    (tmp_path/'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    metadata=Mock();metadata.get_context.return_value=CONTEXT
    service=ApexAutomationService(tmp_path,metadata_factory=lambda org:metadata)
    service.cli=Mock(side_effect=RuntimeError('Metadata access denied'))
    provider=Mock()
    with pytest.raises(RuntimeError):service.generate(ApexRequest(class_name='Example',requirement='Test',objects=['Account']),provider)
    provider.generate.assert_not_called()
