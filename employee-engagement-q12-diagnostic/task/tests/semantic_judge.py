#!/usr/bin/env python3
"""Required source-bound review for open diagnostic meaning."""
import hashlib,json,os
from pathlib import Path
from judge_transport import call as call_responses, response_text

HERE=Path(__file__).resolve().parent

class SemanticUnavailable(RuntimeError): pass
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sha(b):return hashlib.sha256(b if isinstance(b,bytes) else b.encode()).hexdigest()
def validate_decision(value,candidate_text,source_facts):
 rows=value.get('owners',[])
 if len(rows)!=2 or {r.get('id') for r in rows}!={'D5','E6'}:raise SemanticUnavailable('Incomplete semantic owners')
 for row in rows:
  if row.get('score') not in (0,1) or not row.get('rationale'):raise SemanticUnavailable('Invalid semantic decision')
  if row.get('candidate_quote') not in candidate_text or row.get('source_quote') not in source_facts:raise SemanticUnavailable('Unbound semantic quote')
 return {r['id']:r for r in rows}

def review(candidate_text,source_facts):
 prompt=("Judge two open semantic owners from candidate workbook text against supplied source-derived facts. "
         "D5: organization actions must name a real diagnosed pattern, uncertainty/stabilization and a targeted action; keywords or generic improve/monitor text are zero. "
         "E6: limitations must correctly distinguish association from causality, disclose response-rate limits and suppress/qualify n<10; keyword-complete false claims are zero. "
         "Return JSON {owners:[{id:D5|E6,score:0|1,candidate_quote:string,source_quote:string,rationale:string}]}. "
         "Quotes must be exact substrings.\nDATA\n"+canonical({'candidate':candidate_text,'source':source_facts}))
 model=os.environ.get('LLM_JUDGE_MODEL','gpt-5.6-sol')
 if model!='gpt-5.6-sol':raise SemanticUnavailable('Only gpt-5.6-sol Responses judge is accepted')
 body={'model':model,'store':False,'input':[{'role':'user','content':[{'type':'input_text','text':prompt}]}]}
 wire=canonical(body).encode();key=sha(wire);pack=HERE/'golden_replay'/key
 external=Path(os.environ.get('LLM_JUDGE_CACHE_DIR','/logs/verifier/q12-judge-cache'))/key
 root=pack if pack.is_dir() else external
 if root.is_dir():
  if (root/'request.json').read_bytes()!=wire:raise SemanticUnavailable('Stale semantic replay request')
  response=json.loads((root/'response.json').read_text())
 else:
  if os.environ.get('LLM_JUDGE_MODE')=='replay':raise SemanticUnavailable('No exact Golden semantic replay')
  url=os.environ.get('LLM_JUDGE_BASE_URL');token=os.environ.get('LLM_JUDGE_API_KEY')
  if not url or not token:raise SemanticUnavailable('Fresh semantic judge credentials unavailable')
  try:
   timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS','300'))
   response,text=call_responses(body,url,token,timeout,1);raw=canonical(response).encode()
  except Exception as e:raise SemanticUnavailable(type(e).__name__+': '+str(e))
  external.mkdir(parents=True,exist_ok=True);(external/'request.json').write_bytes(wire);(external/'response.json').write_bytes(raw);response=json.loads(raw)
 text=response_text(response)
 try:value=json.loads(text)
 except Exception as e:raise SemanticUnavailable('Invalid semantic JSON: '+str(e))
 return validate_decision(value,candidate_text,source_facts),key
