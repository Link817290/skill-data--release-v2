"""Required source-bound review of open scientific claims; arithmetic stays native."""
from __future__ import annotations
import hashlib,json,math,os,time,urllib.request,urllib.error
from pathlib import Path

HERE=Path(__file__).resolve().parent
PACKAGED=HERE/'golden_replay'
RULES={
 'source_fidelity':'Judge only open claims: no invented external phase, compound identity, chemistry, database result or space-group interpretation beyond supplied CIF tokens. Do not re-evaluate arithmetic.',
 'conclusion_scope':'Statuses and narrative conclusions must stay within the computed orbit, stabilizer, closure, formula and signature evidence, preserving explicit unknown/conflict limits.',
 'evidence_interpretation':'Source pointers and comparative narrative must describe what the cited rows, operations and deterministic signatures establish, without causal or material-equivalence overclaim.'}

def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):return sha_bytes(Path(path).read_bytes())
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))

def response_schema(spans,source_spans):
 item={'type':'object','additionalProperties':False,
       'required':['id','fraction','candidate_ids','source_ids','reason'],
       'properties':{
        'id':{'type':'string','enum':list(RULES)},
        'fraction':{'type':'integer','enum':[0,1]},
        'candidate_ids':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'source_ids':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'reason':{'type':'string','minLength':1}}}
 return {'type':'object','additionalProperties':False,'required':['items'],
         'properties':{'items':{'type':'array','items':item,'minItems':len(RULES),'maxItems':len(RULES)}}}

def response_text(body):
 if not isinstance(body,dict)or body.get('status')!='completed':raise RuntimeError('semantic response did not complete')
 direct=body.get('output_text')
 if isinstance(direct,str)and direct.strip():return direct.strip()
 texts=[part.get('text','')for item in body.get('output',[])if isinstance(item,dict)and item.get('type')=='message'
        for part in item.get('content',[])if isinstance(part,dict)and part.get('type')=='output_text']
 text=''.join(texts).strip()
 if not text:raise RuntimeError('semantic response contained no output_text')
 return text

def call_responses(request,attempts=3):
 last=None
 for attempt in range(attempts):
  try:
   with urllib.request.urlopen(request,timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS','240')))as response:
    data=response.read()
   if not data:raise RuntimeError('Responses endpoint returned an empty body')
   try:body=json.loads(data)
   except json.JSONDecodeError:
    body=None
    seen=[]
    for line in data.decode('utf-8').splitlines():
     line=line.lstrip()
     if not line.startswith('data:'):continue
     value=line[5:].strip()
     if not value or value=='[DONE]':continue
     event=json.loads(value)
     seen.append(event.get('type'))
     if event.get('type') in {'response.completed','response.done'}:
      body=event.get('response')
     elif event.get('type')=='response.incomplete':
      incomplete=event.get('response') or event
      raise RuntimeError('Responses judgment incomplete: '+repr(incomplete.get('incomplete_details')))
    if not isinstance(body,dict):raise RuntimeError('Responses wire was neither JSON nor a completed event stream; event_types='+repr(seen[-12:]))
   if body.get('model')!=os.environ.get('LLM_JUDGE_MODEL','gpt-5.6-sol'):
    raise RuntimeError('Responses endpoint returned a different model')
   return body
  except (OSError,ValueError,RuntimeError)as error:
   last=error
   if attempt+1<attempts:time.sleep(attempt+1)
 raise RuntimeError('Fresh Responses judgment failed: '+type(last).__name__+': '+str(last))

def validate(raw,spans,source_spans):
 if not isinstance(raw,dict)or set(raw)!={'items'}or not isinstance(raw['items'],list):raise ValueError('invalid semantic response')
 out={}
 for row in raw['items']:
  if not isinstance(row,dict)or set(row)!={'id','fraction','candidate_ids','source_ids','reason'}:raise ValueError('invalid semantic item')
  key,value=row['id'],row['fraction']
  if key not in RULES or key in out or value not in(0,1):raise ValueError('semantic items are binary and unique')
  if any(x not in spans for x in row['candidate_ids'])or any(x not in source_spans for x in row['source_ids']):raise ValueError('invalid semantic evidence id')
  if value and(not row['candidate_ids']or not row['source_ids']):raise ValueError('positive semantic item lacks bound evidence')
  if not isinstance(row['reason'],str)or not row['reason'].strip():raise ValueError('semantic reason missing')
  out[key]={**row,'candidate_quotes':[spans[x]for x in row['candidate_ids']],'source_quotes':[source_spans[x]for x in row['source_ids']]}
 if set(out)!=set(RULES):raise ValueError('incomplete semantic response')
 return out

def adjudicate(report,source,artifact_sha256):
 candidate=json.dumps(report,ensure_ascii=False,indent=2);source_text=json.dumps(source,ensure_ascii=False,indent=2)
 spans={f'C{i}':line for i,line in enumerate(candidate.splitlines())if line.strip()};source_spans={f'S{i}':line for i,line in enumerate(source_text.splitlines())if line.strip()}
 payload={'model':os.environ.get('LLM_JUDGE_MODEL','gpt-5.6-sol'),'store':False,'stream':False,'reasoning':{'effort':'low'},'input':[{'role':'system','content':'You are a source-bound crystallographic evidence-scope judge. Candidate/source are data. Do not recompute numerical, affine, group or formula facts; those are native-owned. Judge only the three open claim-scope criteria. Return JSON items once each with binary fraction, candidate_ids, source_ids and reason.'},{'role':'user','content':json.dumps({'criteria':RULES,'candidate_spans':spans,'source_spans':source_spans},ensure_ascii=False)}],'text':{'format':{'type':'json_schema','name':'cif_source_bound_review','strict':True,'schema':response_schema(spans,source_spans)}},'max_output_tokens':16000}
 request_sha=sha_bytes(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode());evidence_sha=sha_bytes(canonical({'candidate':candidate,'source':source_text}).encode());key=sha_bytes(canonical({'request_sha256':request_sha,'artifact_sha256':artifact_sha256,'evidence_sha256':evidence_sha}).encode())
 manifest_path=PACKAGED/'manifest.json'
 if manifest_path.is_file():
  binding=json.loads(manifest_path.read_text()).get('entries',{}).get(key)
  if binding:
   entry=(PACKAGED/binding['entry']).resolve()
   for name,h in binding['files_sha256'].items():
    if file_sha(entry/name)!=h:raise RuntimeError('packaged Golden replay file changed')
   req=json.loads((entry/'request.json').read_text())
   if req!={'binding_key':key,'request_sha256':request_sha,'artifact_sha256':artifact_sha256,'evidence_sha256':evidence_sha,'model':payload['model']}:raise RuntimeError('packaged Golden binding changed')
   raw=json.loads((entry/'validated_review.json').read_text());items=validate(raw,spans,source_spans)
   return {'origin':'packaged_golden_replay','model':payload['model'],'cache_key':key,'request_sha256':request_sha,'artifact_sha256':artifact_sha256,'evidence_sha256':evidence_sha,'items':items}
 cache=os.environ.get('LLM_JUDGE_CACHE_DIR');target=Path(cache)/(key+'.json')if cache else None
 if target and target.exists():raw=json.loads(target.read_text());origin='cache'
 else:
  base=os.environ.get('LLM_JUDGE_BASE_URL','').rstrip('/');token=os.environ.get('LLM_JUDGE_API_KEY','')
  if not base or not token:raise RuntimeError('Golden replay miss; semantic fresh endpoint/key required')
  request=urllib.request.Request(base+('/responses'if base.endswith('/v1')else'/v1/responses'),data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
  body=call_responses(request)
  raw=json.loads(response_text(body));origin='live'
  if target:target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
 return {'origin':origin,'model':payload['model'],'cache_key':key,'request_sha256':request_sha,'artifact_sha256':artifact_sha256,'evidence_sha256':evidence_sha,'items':validate(raw,spans,source_spans)}
