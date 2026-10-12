"""Text generation via fixed official endpoints. No browser keys or auto retries."""
import os
import re
import httpx
from .base import AIProvider


class RestProvider(AIProvider):
    def __init__(self,provider,api_key,model,http=None,max_tokens=None):
        if provider not in {'openai','gemini'}:raise ValueError('Unsupported AI provider.')
        self.provider_name=provider
        self.api_key=(api_key or '').strip()
        self.model=(model or '').removeprefix('models/').strip()
        if not self.api_key or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}',self.model):
            raise ValueError('Provide an API key and valid text model ID in Settings → AI provider.')
        self.http=http
        self.max_tokens=max_tokens or int(os.getenv('AI_MAX_OUTPUT_TOKENS','4096'))
        self.max_input_tokens=int(os.getenv('AI_MAX_INPUT_TOKENS','180000'))
        if self.max_tokens<64 or self.max_input_tokens<1:raise ValueError('Invalid AI token budget.')
        self.usage_events=[];self.generation_attempts=0

    def request(self,path,body):
        base='https://api.openai.com/v1' if self.provider_name=='openai' else 'https://generativelanguage.googleapis.com/v1beta'
        headers={'Authorization':'Bearer '+self.api_key} if self.provider_name=='openai' else {'x-goog-api-key':self.api_key}
        try:
            if self.http is not None:r=self.http.post(base+path,json=body,headers=headers)
            else:
                with httpx.Client(timeout=httpx.Timeout(90,connect=10),follow_redirects=False) as client:
                    r=client.post(base+path,json=body,headers=headers)
        except httpx.HTTPError:raise RuntimeError('AI provider request timed out or failed. Check connectivity and retry explicitly.') from None
        if r.status_code in (401,403):raise RuntimeError('AI provider rejected the key or model access. Review Settings → AI provider.')
        if r.status_code==429:raise RuntimeError('AI provider rate limit or quota reached. Check billing/quota before retrying.')
        if r.status_code!=200:raise RuntimeError(f'AI provider request failed (HTTP {r.status_code}). Check model compatibility and provider availability.')
        try:result=r.json()
        except ValueError:raise RuntimeError('AI provider returned unreadable data.') from None
        if not isinstance(result,dict):raise RuntimeError('AI provider returned invalid data.')
        return result

    def generate(self,system_prompt,user_prompt):
        if self.provider_name=='openai':
            payload=dict(model=self.model,instructions=system_prompt,input=user_prompt)
            count=self.request('/responses/input_tokens',payload).get('input_tokens')
        else:
            payload=dict(systemInstruction={'parts':[{'text':system_prompt}]},contents=[{'role':'user','parts':[{'text':user_prompt}]}])
            count=self.request(f'/models/{self.model}:countTokens',{'generateContentRequest':{'model':'models/'+self.model,**payload}}).get('totalTokens')
        if not isinstance(count,int) or isinstance(count,bool) or count<0:raise RuntimeError('AI provider did not return a valid input token count.')
        if count>self.max_input_tokens:raise ValueError('AI planning input exceeds the configured input budget. Reduce the selected org context; no generation request was sent.')
        self.generation_attempts+=1
        if self.provider_name=='openai':
            r=self.request('/responses',{**payload,'max_output_tokens':self.max_tokens,'store':False})
            u=r.get('usage') or {};cached=(u.get('input_tokens_details') or {}).get('cached_tokens',0) or 0
            self.usage_events.append(dict(provider='openai',model=r.get('model',self.model),input_tokens=max(0,(u.get('input_tokens',0) or 0)-cached),output_tokens=u.get('output_tokens',0) or 0,cache_read_input_tokens=cached))
            if not u:self.usage_events[-1]=None
            if r.get('status')!='completed':raise RuntimeError('OpenAI response was incomplete or refused. Check the output budget and request before retrying.')
            texts=[p['text'] for item in r.get('output',[]) if item.get('type')=='message' for p in item.get('content',[]) if p.get('type')=='output_text' and isinstance(p.get('text'),str)]
        else:
            r=self.request(f'/models/{self.model}:generateContent',{**payload,'generationConfig':{'maxOutputTokens':self.max_tokens,'candidateCount':1}})
            u=r.get('usageMetadata') or {};cached=u.get('cachedContentTokenCount',0) or 0
            self.usage_events.append(dict(provider='gemini',model=r.get('modelVersion',self.model),input_tokens=max(0,(u.get('promptTokenCount',0) or 0)-cached),output_tokens=(u.get('candidatesTokenCount',0) or 0)+(u.get('thoughtsTokenCount',0) or 0),cache_read_input_tokens=cached))
            if not u:self.usage_events[-1]=None
            candidates=r.get('candidates') or []
            if not candidates or candidates[0].get('finishReason')!='STOP':raise RuntimeError('Gemini response was blocked or incomplete. Check the output budget and request before retrying.')
            texts=[p['text'] for p in candidates[0].get('content',{}).get('parts',[]) if not p.get('thought') and isinstance(p.get('text'),str)]
        text='\n'.join(texts).strip()
        if not text:raise RuntimeError('AI provider returned no usable text.')
        return text
