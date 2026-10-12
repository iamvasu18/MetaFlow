import httpx
import pytest
from fastapi import HTTPException
from Backend.AI.app.providers.rest_provider import RestProvider
from Backend.AI.app.services import integration_service as integrations

@pytest.mark.parametrize('provider',['openai','gemini'])
def test_official_transport_count_and_text(provider):
    calls=[]
    def handler(request):
        calls.append(request)
        assert 'secret' not in str(request.url)
        if 'input_tokens' in request.url.path:return httpx.Response(200,json={'input_tokens':10})
        if 'countTokens' in request.url.path:return httpx.Response(200,json={'totalTokens':10})
        if provider=='openai':return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'valid plan'}]}],'usage':{'input_tokens':10,'output_tokens':3}})
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'private thought'},{'text':'valid plan'}]}}],'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':3,'thoughtsTokenCount':2}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        p=RestProvider(provider,'secret','text-model',http=http)
        assert p.generate('system','user')=='valid plan'
        assert len(calls)==2
        assert p.generation_attempts==1
        assert p.usage_events[0]['input_tokens']==10
        assert p.usage_events[0]['output_tokens']==(3 if provider=='openai' else 5)
        assert calls[0].headers.get('Authorization')=='Bearer secret' if provider=='openai' else calls[0].headers['x-goog-api-key']=='secret'

@pytest.mark.parametrize('status',[400,401,403,429,500])
def test_provider_error_sanitized_and_not_retried(status):
    calls=[]
    def handler(r):calls.append(r);return httpx.Response(status,json={'error':{'message':'secret api_key user data'}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(RuntimeError) as e:RestProvider('openai','secret','model',http=http).generate('s','u')
    assert 'secret' not in str(e.value)
    assert len(calls)==1


def test_budget_prevents_generation():
    calls=[]
    def handler(r):calls.append(r);return httpx.Response(200,json={'input_tokens':999999})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ValueError):RestProvider('openai','secret','model',http=http).generate('s','u')
    assert len(calls)==1

@pytest.mark.parametrize('provider',['openai','gemini'])
def test_truncation_not_accepted(provider):
    def handler(r):
        if 'input_tokens' in r.url.path:return httpx.Response(200,json={'input_tokens':1})
        if 'countTokens' in r.url.path:return httpx.Response(200,json={'totalTokens':1})
        return httpx.Response(200,json={'status':'incomplete','candidates':[{'finishReason':'MAX_TOKENS'}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        p=RestProvider(provider,'secret','model',http=http)
        with pytest.raises(RuntimeError):p.generate('s','u')
        assert len(p.usage_events)==1


def test_provider_switch_needs_new_key(monkeypatch):
    monkeypatch.setattr(integrations,'ai_settings',lambda owner:{'provider':'anthropic','api_key':'claude-secret'})
    with pytest.raises(HTTPException) as e:integrations.verify_ai('owner','','model','openai')
    assert e.value.status_code==422


def test_verified_account_settings_saved_without_public_key(monkeypatch):
    captured=[]
    monkeypatch.setattr(integrations,'ai_settings',lambda owner:{'provider':'gemini','api_key':'old'})
    monkeypatch.setattr(RestProvider,'generate',lambda self,*args:'OK')
    monkeypatch.setattr(integrations,'save_settings',lambda owner,kind,value:captured.append((owner,kind,value)))
    public=integrations.verify_ai('owner','secret','models/gemini-example','gemini')
    assert public['provider']=='gemini' and public['model']=='gemini-example'
    assert 'api_key' not in public
    assert captured[0][0]=='owner' and captured[0][2]['api_key']=='secret'


def test_factory_routes_account_provider(monkeypatch):
    from Backend.AI.app.providers.provider_factory import get_ai_provider
    from Backend.AI.app.account_api import current_account
    monkeypatch.setattr(integrations,'ai_settings',lambda owner:{'provider':'openai','api_key':'secret','model':'text-model'})
    token=current_account.set('owner')
    try:assert get_ai_provider().provider_name=='openai'
    finally:current_account.reset(token)
