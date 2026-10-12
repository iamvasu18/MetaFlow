import json
import pytest
from Backend.AI.app.services.source_reuse_service import inspect_reuse
from Backend.AI.app.services.conversation_service import respond,ConversationTurn
class Provider:
    def __init__(self,replies):self.replies=replies;self.calls=[]
    def generate(self,**kw):self.calls.append(kw);return json.dumps(self.replies[len(self.calls)-1])
class Api:
    def __init__(self):self.queries=[]
    def query(self,q,tooling=False):
        self.queries.append(q);assert tooling
        if 'SELECT Id, DeveloperName' in q:return {'records':[{'Id':'0Rb000000000001AAA','DeveloperName':'objectFieldSearcher','NamespacePrefix':None}]}
        if 'LightningComponentResource' in q:return {'records':[{'FilePath':'lwc/objectFieldSearcher/objectFieldSearcher.js','Source':'export default class Searcher { searchObjects() { return this.objects.filter(o => o.label.includes(this.search)); } }'}]}
        if 'SELECT Id, Name' in q:return {'records':[{'Id':'01p000000000001AAA','Name':'AccountService','NamespacePrefix':None}]}
        if 'SELECT Body' in q:return {'records':[{'Body':'public inherited sharing class AccountService { public static List<Account> getAccounts(){ return [SELECT Name FROM Account WITH USER_MODE LIMIT 10]; } }'}]}
        pytest.fail(q)
def test_named_lwc_reads_source_not_just_name():
    p=Provider([{'match':True,'matchingComponents':['objectFieldSearcher'],'response':'objectFieldSearcher implements a searchObjects filter. Reuse it unchanged or create a separate component?'}]);api=Api()
    result=inspect_reuse(api,'LightningComponentBundle','Search all objects',p,'Object Field Searcher')
    assert result['match'] and result['reviewed']==['objectFieldSearcher']
    assert len(api.queries)==2 and 'LightningComponentBundleId' in api.queries[1]
    assert 'searchObjects' in p.calls[0]['user_prompt']
def test_functional_search_uses_bounded_candidates_then_reads_apex_body():
    p=Provider([{'candidates':['AccountService']},{'match':True,'matchingComponents':['AccountService'],'response':'AccountService retrieves up to ten Accounts. Would you like to reuse it?'}]);api=Api()
    assert inspect_reuse(api,'ApexClass','Get ten Accounts',p)['match']
    assert 'WITH USER_MODE' in p.calls[1]['user_prompt']
def test_hallucinated_candidate_is_rejected_before_source_query():
    p=Provider([{'candidates':['InventedClass']}]);api=Api()
    with pytest.raises(ValueError,match='unverified'):inspect_reuse(api,'ApexClass','Get Accounts',p)
    assert len(api.queries)==1
def test_unreadable_code_cannot_support_reuse_claim():
    class Hidden(Api):
        def query(self,q,tooling=False):return {'records':[{'Body':None}]} if 'SELECT Body' in q else super().query(q,tooling)
    p=Provider([{'match':True,'matchingComponents':['AccountService'],'response':'Reuse AccountService.'}])
    with pytest.raises(ValueError,match='readable source'):inspect_reuse(Hidden(),'ApexClass','Get Accounts',p,'AccountService')
def test_new_code_requirement_stops_for_source_supported_reuse_question():
    p=Provider([
        {'action':'build','requirement':'Create Account getter class','code_kind':'ApexClass'},
        {'candidates':['AccountService']},
        {'match':True,'matchingComponents':['AccountService'],'response':'AccountService already retrieves Accounts. Reuse it or create a separate class?'}])
    result=respond(ConversationTurn(target_org='org',message='Create an Apex getter for Accounts'),p,lambda:Api())
    assert result['action']=='clarify'
    assert 'AccountService' in result['response']

def test_explicit_reuse_acknowledges_without_repeating_choice():
    class Inventory(Api):
        def list_components(self,kind):return [{'fullName':'AccountService'}]
    p=Provider([{'action':'answer','response':'Reuse it','code_kind':'ApexClass','reuse_decision':'reuse','components':[{'type':'ApexClass','name':'AccountService'}]}])
    result=respond(ConversationTurn(target_org='org',message='Reuse AccountService unchanged'),p,lambda:Inventory())
    assert result['action']=='answer'
    assert 'AccountService' in result['response'] and 'unchanged' in result['response']
    assert len(p.calls)==1
