from __future__ import annotations
import json,os,time,urllib.request
def responses_json(payload,validate,transform=lambda x:x):
 model=payload.get('model','')
 if not model.startswith('gpt-'):raise RuntimeError('required judge model must be GPT')
 base=os.environ.get('LLM_JUDGE_BASE_URL','').rstrip('/');key=os.environ.get('LLM_JUDGE_API_KEY','')
 if not base or not key:raise RuntimeError('OpenAI Responses endpoint and credential are required')
 url=base+('/responses' if base.endswith('/v1') else '/v1/responses');timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS','240'));attempts=3
 for n in range(attempts):
  try:
   req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key});body=json.load(urllib.request.urlopen(req,timeout=timeout))
   if body.get('status')!='completed':raise ValueError('Responses request incomplete')
   text=''.join(p.get('text','') for x in body.get('output',[]) if x.get('type')=='message' for p in x.get('content',[]) if p.get('type')=='output_text').strip();text=text.split('\n',1)[1].rsplit('```',1)[0] if text.startswith('```') else text;raw=transform(json.loads(text));validate(raw);return raw
  except Exception as e:
   if n+1==attempts:raise RuntimeError(f'Responses judge failed after {attempts} attempts: {e}') from e
   time.sleep(2*(n+1))
