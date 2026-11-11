"""Required source-bound review of open engineering claims; calculations stay native."""
from __future__ import annotations
import hashlib,json,os,urllib.error,urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent;PACKAGED=HERE/'golden_replay'
RULES={
 'source_fidelity':'No invented standard, catalog, test result, operating condition or equipment fact beyond the supplied workbook/instruction.',
 'conclusion_scope':'Narrative/formula text limits conclusions to the supplied operating cases, empirical correlations and computed adequacy checks; it does not claim causal or universal performance. A verdict located in the same identified CASE sheet and directly controlled by that case calculation is scoped to that case unless the candidate adds cross-condition, universal or causal language.',
 'evidence_binding':'Engineering verdict text refers to the corresponding computed selection, pressure/power or specific-power evidence and does not contradict or overstate it.'}
MODEL='gpt-5.6-sol'
SCHEMA={
 'type':'object','additionalProperties':False,'required':['items'],'properties':{
  'items':{'type':'array','minItems':3,'maxItems':3,'uniqueItems':True,'items':{
   'type':'object','additionalProperties':False,
   'required':['id','fraction','candidate_ids','source_ids','reason'],
   'properties':{
    'id':{'type':'string','enum':list(RULES)},
    'fraction':{'type':'integer','enum':[0,1]},
    'candidate_ids':{'type':'array','uniqueItems':True,'items':{'type':'string','pattern':'^C[0-9]+$'}},
    'source_ids':{'type':'array','uniqueItems':True,'items':{'type':'string','pattern':'^S[0-9]+$'}},
    'reason':{'type':'string','minLength':1}
   }
  }}
 }}
class SemanticJudgeError(RuntimeError):pass
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def fsha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def validate(raw,cand,src):
 if not isinstance(raw,dict)or set(raw)!={'items'}or not isinstance(raw['items'],list):raise SemanticJudgeError('invalid semantic response')
 out={}
 for row in raw['items']:
  if not isinstance(row,dict)or set(row)!={'id','fraction','candidate_ids','source_ids','reason'}or row['id']not in RULES or row['id']in out or type(row['fraction'])is not int or row['fraction']not in(0,1):raise SemanticJudgeError('invalid semantic item')
  if not isinstance(row['candidate_ids'],list)or not isinstance(row['source_ids'],list)or any(type(x)is not str or x not in cand for x in row['candidate_ids'])or any(type(x)is not str or x not in src for x in row['source_ids']):raise SemanticJudgeError('invalid evidence id')
  if len(row['candidate_ids'])!=len(set(row['candidate_ids']))or len(row['source_ids'])!=len(set(row['source_ids'])):raise SemanticJudgeError('duplicate evidence id')
  if not isinstance(row['reason'],str)or not row['reason'].strip():raise SemanticJudgeError('semantic reason missing')
  if row['fraction']and(not row['candidate_ids']or not row['source_ids']):raise SemanticJudgeError('positive semantic item lacks evidence')
  out[row['id']]={**row,'candidate_quotes':[cand[x]for x in row['candidate_ids']],'source_quotes':[src[x]for x in row['source_ids']]}
 if set(out)!=set(RULES):raise SemanticJudgeError('incomplete semantic response')
 return out
def response_text(body,model):
 if not isinstance(body,dict)or body.get('status')!='completed':raise SemanticJudgeError('Responses request did not complete')
 if body.get('error')not in(None,{}):raise SemanticJudgeError('Responses request returned an error')
 if body.get('incomplete_details')not in(None,{}):raise SemanticJudgeError('Responses request is incomplete')
 if body.get('model')!=model:raise SemanticJudgeError('Responses judge returned a different model')
 output=body.get('output')
 if not isinstance(output,list):raise SemanticJudgeError('Responses output is missing')
 messages=[item for item in output if isinstance(item,dict)and item.get('type')=='message']
 final=[item for item in messages if item.get('phase')=='final_answer']or messages
 if len(final)!=1:raise SemanticJudgeError('Responses output has no unique final message')
 content=final[0].get('content')
 if not isinstance(content,list)or any(not isinstance(part,dict)for part in content):raise SemanticJudgeError('Responses message content is malformed')
 if any(part.get('type')=='refusal' for part in content):raise SemanticJudgeError('Responses judge refused the measurement')
 texts=[part.get('text')for part in content if part.get('type')=='output_text']
 if len(texts)!=1 or not isinstance(texts[0],str)or not texts[0].strip():raise SemanticJudgeError('Responses output has no unique output_text')
 try:return json.loads(texts[0])
 except json.JSONDecodeError as error:raise SemanticJudgeError('Responses output_text is not JSON')from error
def adjudicate(candidate,source,artifact_sha256):
 ctext=json.dumps(candidate,ensure_ascii=False,indent=2);stext=json.dumps(source,ensure_ascii=False,indent=2);cand={f'C{i}':x for i,x in enumerate(ctext.splitlines())if x.strip()};src={f'S{i}':x for i,x in enumerate(stext.splitlines())if x.strip()}
 model=os.environ.get('LLM_JUDGE_MODEL',MODEL)
 mode=os.environ.get('LLM_JUDGE_MODE','fresh')
 if mode not in('fresh','replay'):raise SemanticJudgeError('LLM_JUDGE_MODE must be fresh or replay')
 timeout=float(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS') or os.environ.get('LLM_JUDGE_TIMEOUT_SEC') or '600')
 if not 0 < timeout <= 3600:raise SemanticJudgeError('LLM_JUDGE_TIMEOUT_SECONDS must be in (0, 3600]')
 if model!=MODEL:raise SemanticJudgeError('only gpt-5.6-sol Responses judge is accepted')
 payload={'model':model,'store':False,'reasoning':{'effort':'high'},'input':[{'role':'developer','content':[{'type':'input_text','text':'Judge only open engineering claim scope and source fidelity. Numerical formulas, selection, physics and structure are native-owned and must not be rejudged. Return all three binary items. Positive credit requires candidate and source span IDs.'}]},{'role':'user','content':[{'type':'input_text','text':json.dumps({'criteria':RULES,'candidate_spans':cand,'source_spans':src},ensure_ascii=False)}]}],'text':{'format':{'type':'json_schema','name':'cooling_tower_open_claim_review','strict':True,'schema':SCHEMA}},'max_output_tokens':3000}
 request_sha=digest(payload);evidence_sha=digest({'candidate':ctext,'source':stext});key=digest({'request_sha256':request_sha,'artifact_sha256':artifact_sha256,'evidence_sha256':evidence_sha})
 mp=PACKAGED/'manifest.json'
 if mp.is_file():
  b=json.loads(mp.read_text()).get('entries',{}).get(key)
  if b:
   e=(PACKAGED/b['entry']).resolve()
   for n,h in b['files_sha256'].items():
    if fsha(e/n)!=h:raise RuntimeError('packaged Golden replay changed')
   req=json.loads((e/'request.json').read_text())
   binding={'binding_key':key,'request_sha256':request_sha,'artifact_sha256':artifact_sha256,'evidence_sha256':evidence_sha,'model':payload['model']}
   if req.get('binding')!=binding or req.get('body')!=payload:raise RuntimeError('packaged Golden binding changed')
   body=json.loads((e/'raw_response.json').read_text())
   if response_text(body,model)!=json.loads((e/'validated_review.json').read_text()):raise RuntimeError('packaged Golden response changed')
   raw=json.loads((e/'validated_review.json').read_text())
   return {'origin':'packaged_golden_replay','cache_key':key,'items':validate(raw,cand,src)}
 cache=os.environ.get('LLM_JUDGE_CACHE_DIR');target=Path(cache)/key if cache else None
 if target and (target/'validated_review.json').exists():raw=json.loads((target/'validated_review.json').read_text());origin='cache'
 else:
  if mode=='replay':raise SemanticJudgeError('Golden replay miss; semantic fresh call disabled in replay mode')
  base=os.environ.get('LLM_JUDGE_BASE_URL','').rstrip('/');token=os.environ.get('LLM_JUDGE_API_KEY','')
  if not base or not token:raise SemanticJudgeError('Golden replay miss; semantic fresh endpoint/key required')
  url=base if base.endswith('/v1/responses')else base+('/responses'if base.endswith('/v1')else'/v1/responses')
  req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
  try:
   with urllib.request.urlopen(req,timeout=timeout)as response:body=json.load(response)
  except (OSError,urllib.error.URLError,json.JSONDecodeError)as error:raise SemanticJudgeError('Responses API/protocol failure: '+type(error).__name__)from error
  raw=response_text(body,model);origin='live'
  if target:
   target.mkdir(parents=True,exist_ok=True)
   binding={'binding_key':key,'request_sha256':request_sha,'artifact_sha256':artifact_sha256,'evidence_sha256':evidence_sha,'model':payload['model']}
   (target/'request.json').write_text(json.dumps({'binding':binding,'body':payload},ensure_ascii=False,indent=2)+'\n')
   (target/'raw_response.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
   (target/'validated_review.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
   (target/'validation.json').write_text(json.dumps({'status':'qualified','protocol':'OpenAI Responses /v1/responses','returned_model':body.get('model'),'response_id':body.get('id')},indent=2)+'\n')
 return {'origin':origin,'cache_key':key,'request_sha256':request_sha,'artifact_sha256':artifact_sha256,'evidence_sha256':evidence_sha,'items':validate(raw,cand,src)}
