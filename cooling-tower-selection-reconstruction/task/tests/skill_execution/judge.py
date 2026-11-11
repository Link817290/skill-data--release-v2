"""Portable observable-process diagnostic with bound real-call caches."""
import argparse
import ast
import copy
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from runtime import core

HERE=Path(__file__).resolve().parent
VERSION='cooling-skill-process-4'


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=path.parent,encoding='utf-8',delete=False)as stream:
  stream.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');temporary=Path(stream.name)
 temporary.replace(path)


def sanitize(text):
 text=core.redact(text)
 text=re.sub(r'(?i)\b(?:codex|claude[- ]code)\b','[EXCLUDED_HARNESS]',text)
 text=re.sub(r'(?i)\b[A-Z_]*(?:API_KEY|AUTH_TOKEN|PASSWORD|SECRET)[A-Z_]*\s*[:=]\s*[^\s,;]+','[REDACTED_CREDENTIAL]',text)
 return re.sub(r'/mnt/A/[^/\s]+','/mnt/A/[REDACTED_USER]',text)


def excerpt(text,limit):
 text=sanitize(text).strip()
 if len(text)<=limit:return text,False
 half=(limit-40)//2
 return text[:half]+'\n...[MIDDLE EXCERPT OMITTED]...\n'+text[-half:],True


def visible_text(value):
 if value is None:return''
 if isinstance(value,str):
  stripped=value.strip()
  if stripped.startswith(('{','[','"',"'")):
   for parser in [json.loads,ast.literal_eval]:
    try:decoded=parser(stripped)
    except (ValueError,SyntaxError,TypeError,MemoryError,RecursionError):continue
    if isinstance(decoded,(dict,list))or isinstance(decoded,str)and decoded!=value:return visible_text(decoded)
  return value
 if isinstance(value,list):return'\n\n'.join(visible_text(item)for item in value)
 if isinstance(value,dict):return'\n'.join(str(key)+':\n'+visible_text(item)for key,item in value.items())
 return str(value)


def observable_trace(trajectory,settings):
 blocks={};clipped=[];excluded=[]
 if not isinstance(trajectory,dict)or not isinstance(trajectory.get('steps'),list):raise ValueError('Trusted trajectory requires a steps array')
 for index,step in enumerate(trajectory['steps'],1):
  if step.get('source',step.get('role'))not in ['agent','assistant']:
   excluded.append(index);continue
  step_id=step.get('step_id',index)
  if isinstance(step_id,bool)or not isinstance(step_id,int)or step_id<1:step_id=index
  lines=[f'STEP {step_id} [agent]'];messages=core.stringify(step.get('message',step.get('content','')))
  message,cut=excerpt(messages,settings['message_chars'])
  if cut:clipped.append({'step_id':step_id,'field':'message'})
  if message:lines.extend(['MESSAGE:',message])
  calls=step.get('tool_calls')or[];visible_calls=[];skill_only=bool(calls)
  for call in calls:
   name=core.tool_name(call)
   if name.lower()=='skill':continue
   skill_only=False;arguments=core.tool_arguments(call)
   if isinstance(arguments,str):
    try:parsed=json.loads(arguments)
    except (json.JSONDecodeError,TypeError):parsed=None
    if isinstance(parsed,(dict,list)):arguments=parsed
   arguments,cut=excerpt(visible_text(arguments),settings['tool_argument_chars'])
   if cut:clipped.append({'step_id':step_id,'field':'tool_arguments'})
   visible_calls.append('TOOL '+name+':\n'+arguments)
  if skill_only:excluded.append(step_id);continue
  lines.extend(visible_calls)
  observation,cut=excerpt(visible_text(step.get('observation','')),settings['observation_chars'])
  if cut:clipped.append({'step_id':step_id,'field':'observation'})
  if observation and core.SKILL_MARKER not in observation.lower():lines.extend(['OBSERVATION:',observation])
  if len(lines)==1:excluded.append(step_id);continue
  if step_id in blocks:raise ValueError('Duplicate observable step identifier')
  blocks[step_id]='\n'.join(lines)
 if not blocks:raise ValueError('No observable execution after removing setup and hidden reasoning')
 trace='\n\n'.join(blocks.values())
 if len(trace)>settings['max_trace_chars']:raise ValueError('Configured trace limit would omit action steps; increase the limit before judging')
 return trace,blocks,{'raw_step_count':len(trajectory['steps']),'visible_step_ids':list(blocks),'excluded_nonexecution_step_ids':excluded,'clipped_fields':clipped,'hidden_reasoning_excluded':True,'setup_and_identity_labels_excluded':True}


def context(trajectory,artifact):
 task=HERE.parent.parent;contract=core.validate_contract(load(HERE/'contract.json'));settings=load(HERE/'settings.json')
 settings['model']=os.environ.get('LLM_JUDGE_MODEL')or settings['model']
 settings['timeout_sec']=float(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS')or os.environ.get('LLM_JUDGE_TIMEOUT_SEC')or settings['timeout_sec'])
 if not 0 < settings['timeout_sec'] <= 3600:raise ValueError('LLM_JUDGE_TIMEOUT_SECONDS must be in (0, 3600]')
 source=load(trajectory);trace,blocks,scope=observable_trace(source,settings)
 skills=[]
 for path in sorted((task/'environment/skills').rglob('*')):
  if path.is_file()and path.suffix in ['.md','.py']:skills.append((str(path.relative_to(task/'environment/skills')),path.read_text(encoding='utf-8')))
 template=(HERE/'prompt.md').read_text();schema=load(HERE/'response.schema.json')
 prompt=template+'\n\nFROZEN PROCEDURAL CONTRACT:\n'+json.dumps(contract,ensure_ascii=False,indent=2)+'\n\nRESPONSE SCHEMA:\n'+json.dumps(schema,ensure_ascii=False,indent=2)+'\n\nTASK INSTRUCTION:\n'+(task/'instruction.md').read_text()+'\n\nSUPPLIED SKILLS AND PUBLIC HELPERS:\n'+'\n\n'.join(label+'\n'+text for label,text in skills)+'\n\nSANITIZED OBSERVABLE TRAJECTORY:\n'+trace
 identity={'judge_version':VERSION,'trajectory_sha256':sha(trajectory),'artifact_sha256':sha(artifact)if artifact else None,'runtime_sha256':{name:sha(HERE/name)for name in ['judge.py','runtime/core.py','contract.json','settings.json','prompt.md','response.schema.json']},'instruction_sha256':sha(task/'instruction.md'),'skill_sha256':{label:hashlib.sha256(text.encode()).hexdigest()for label,text in skills},'sanitized_trace_sha256':hashlib.sha256(trace.encode()).hexdigest(),'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'settings':settings,'visible_step_ids':list(blocks)}
 return {'identity':identity,'key':digest(identity),'contract':contract,'settings':settings,'prompt':prompt,'blocks':blocks,'scope':scope,'trace':trace}


def validate(decision,ctx):
 if not isinstance(decision,dict):raise ValueError('Process judgment is not a JSON object')
 normalized=copy.deepcopy(decision);stripped=copy.deepcopy(decision)
 for name,item in stripped.get('dimensions',{}).items():
  if set(item)!={'level','evidence_step_ids','evidence_quotes','reason'}:raise ValueError('Invalid dimension fields: '+name)
  quotes=item.pop('evidence_quotes')
  if not isinstance(quotes,list):raise ValueError('Evidence quotations must be a list')
  for quote in quotes:
   if not isinstance(quote,dict)or set(quote)!={'step_id','quote'}:raise ValueError('Invalid quotation fields')
   quote['step_id']=core.normalise_step_ids([quote['step_id']],'quotation step')[0]
  normalized['dimensions'][name]['evidence_quotes']=quotes
 checked=core.validate_response(stripped,ctx['contract'],set(ctx['blocks']))
 for name,item in checked['dimensions'].items():
  quotes=normalized['dimensions'][name]['evidence_quotes'];normalized['dimensions'][name]['evidence_step_ids']=item['evidence_step_ids']
  if item['level']>0 and not quotes:raise ValueError('Nonzero level requires a visible execution quotation: '+name)
  for quote in quotes:
   step_id=quote['step_id'];text=quote['quote']
   if step_id not in item['evidence_step_ids']or step_id not in ctx['blocks']:raise ValueError('Quotation cites an unbound step')
   if not isinstance(text,str)or len(text)<8 or text not in ctx['blocks'][step_id]:raise ValueError('Quotation is not an exact visible substring for '+name+' at STEP '+str(step_id)+'. Use a shorter exact snippet of at least8 characters from that step.')
   block=ctx['blocks'][step_id];starts=[block.index(marker)for marker in ['TOOL ','OBSERVATION:']if marker in block]
   if not starts or text not in block[min(starts):]:raise ValueError('A self-certification message is not execution evidence')
 normalized['fatal_flags']=checked['fatal_flags']
 return normalized,checked


def endpoint():
 value=(os.environ.get('LLM_JUDGE_BASE_URL')or'').rstrip('/')
 if not value:raise ValueError('Fresh mode requires LLM_JUDGE_BASE_URL')
 if not value.endswith('/responses'):value+='/responses'if value.endswith('/v1')else'/v1/responses'
 return value


def call(body,settings):
 token=os.environ.get('LLM_JUDGE_API_KEY')
 if not token:raise ValueError('Fresh mode requires LLM_JUDGE_API_KEY')
 request=urllib.request.Request(endpoint(),data=canonical(body).encode(),headers={'content-type':'application/json','authorization':'Bearer '+token},method='POST')
 try:
  with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=settings['timeout_sec'])as response:return json.loads(response.read().decode('utf-8'))
 except urllib.error.HTTPError as error:
  response_text=error.read().decode('utf-8',errors='replace')
  failure=RuntimeError('Judge HTTP '+str(error.code));failure.provider_response={'http_status':error.code,'body':response_text};raise failure from None


def parse(raw):
 if raw.get('status') not in (None, 'completed'):raise ValueError('Judge response did not complete')
 text='\n'.join(part.get('text','') for item in raw.get('output',[]) if item.get('type')=='message' for part in item.get('content',[]) if part.get('type')=='output_text')
 return core.extract_json(text)


def review(trajectory,output,cache,mode='replay',refresh=False,artifact=None):
 output.mkdir(parents=True,exist_ok=True)
 for name in ['skill_execution_result.json','llm_judge_result.json','skill_execution_status.json']:(output/name).unlink(missing_ok=True)
 ctx=context(trajectory,artifact);cache.mkdir(parents=True,exist_ok=True)
 index=load(cache/'index.json')if(cache/'index.json').is_file()else{'entries':{}};record=index['entries'].get(ctx['key'])
 if record and not refresh:
  entry=(cache/record['path']).resolve()
  if not entry.is_relative_to(cache.resolve()):raise ValueError('Cache path escapes its trusted root')
  for name,expected in record['files_sha256'].items():
   if sha(entry/name)!=expected:raise ValueError('Cached judge record changed: '+name)
  request=load(entry/'request.json')
  if request['identity']!=ctx['identity']:raise ValueError('Cached process input binding changed')
  expected_body={'model':ctx['settings']['model'],'max_output_tokens':ctx['settings']['max_tokens'],'input':[{'role':'user','content':ctx['prompt']}],'store':False}
  if request['body']!=expected_body:raise ValueError('Cached process request differs')
  decision,checked=validate(parse(load(entry/'response.json')),ctx)
  if decision!=load(entry/'decision.json')or load(entry/'validation.json')['status']!='validated':raise ValueError('Cached response validation differs')
  origin='offline_replay'
 else:
  if mode!='fresh':raise ValueError('Process cache miss; no process score is invented')
  messages=[{'role':'user','content':ctx['prompt']}];decision=None;errors=[]
  for attempt in range(1,ctx['settings']['max_attempts']+1):
   entry=cache/ctx['key']/uuid.uuid4().hex;body={'model':ctx['settings']['model'],'max_output_tokens':ctx['settings']['max_tokens'],'input':copy.deepcopy(messages),'store':False}
   write(entry/'request.json',{'cache_key':ctx['key'],'identity':ctx['identity'],'body':body,'request_body_sha256':digest(body),'created_at':now(),'evidence_scope':ctx['scope'],'endpoint_configuration':'LLM_JUDGE_BASE_URL; credential is never serialized'})
   write(entry/'sanitized_trajectory.json',{'steps':ctx['blocks'],'text':ctx['trace'],'scope':ctx['scope']})
   started=now();raw=None
   try:
    raw=call(body,ctx['settings']);write(entry/'response.json',raw)
    decision,checked=validate(parse(raw),ctx);write(entry/'decision.json',decision)
    write(entry/'validation.json',{'status':'validated','actual_live_call':True,'started_at':started,'finished_at':now(),'returned_model':raw.get('model'),'response_id':raw.get('id'),'usage':raw.get('usage'),'visible_step_ids_verified':True,'all_nonzero_evidence_quotations_verified':True,'trajectory_sha256':ctx['identity']['trajectory_sha256'],'artifact_sha256':ctx['identity']['artifact_sha256'],'response_sha256':sha(entry/'response.json')})
    break
   except Exception as error:
    if getattr(error,'provider_response',None) is not None:write(entry/'http_error.json',error.provider_response)
    write(entry/'validation.json',{'status':'rejected','live_mode_attempted':True,'started_at':started,'finished_at':now(),'error_type':type(error).__name__,'error':str(error)})
    errors.append(str(error))
    if attempt==ctx['settings']['max_attempts']:raise RuntimeError('No qualified process judgment after actual attempts: '+'; '.join(errors))from error
    if raw is not None:
     text='\n'.join(part.get('text','') for item in raw.get('output',[]) if item.get('type')=='message' for part in item.get('content',[]) if part.get('type')=='output_text')
     messages.extend([{'role':'assistant','content':text},{'role':'user','content':'The response failed evidence/schema validation: '+str(error)+'. Return corrected JSON only. Copy quotations exactly from the cited TOOL/OBSERVATION evidence; use level0 when execution evidence is absent.'}])
    else:time.sleep(min(15,3*attempt))
  record={'path':str(entry.relative_to(cache)),'files_sha256':{name:sha(entry/name)for name in ['request.json','response.json','decision.json','validation.json','sanitized_trajectory.json']}}
  with(cache/'.index.lock').open('a')as lock:
   fcntl.flock(lock,fcntl.LOCK_EX);index=load(cache/'index.json')if(cache/'index.json').is_file()else{'entries':{}};index['entries'][ctx['key']]=record;write(cache/'index.json',index)
  origin='fresh_actual_call'
 raw_score,process,dimensions=core.calculate_score(checked,ctx['contract'])
 for item in dimensions:item['evidence_quotes']=decision['dimensions'][item['id']]['evidence_quotes']
 result={'schema_version':'skill-execution-result-v1','judge_version':VERSION,'status':'measured','process_score':process,'reward_process':process,'reward_process_raw':raw_score,'dimensions':dimensions,'fatal_flags':decision['fatal_flags'],'overall_assessment':decision['overall_assessment'],'confidence':decision['confidence'],'limitations':decision['limitations'],'trajectory_sha256':ctx['identity']['trajectory_sha256'],'artifact_sha256':ctx['identity']['artifact_sha256'],'contract_sha256':ctx['identity']['runtime_sha256']['contract.json'],'cache_key':ctx['key'],'cache_provenance':{'origin':origin,**record},'artifact_rewards_modified':False,'evidence_scope':ctx['scope']}
 write(output/'skill_execution_result.json',result);write(output/'llm_judge_result.json',result);write(output/'skill_execution_status.json',{'status':'measured','judge_version':VERSION,'cache_key':ctx['key']});return result


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--trajectory',type=Path,required=True);parser.add_argument('--artifact',type=Path);parser.add_argument('--mode',choices=['fresh','replay'],required=True);parser.add_argument('--refresh',action='store_true');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--cache-dir',type=Path,required=True);args=parser.parse_args()
 try:result=review(args.trajectory,args.output,args.cache_dir,args.mode,args.refresh,args.artifact)
 except Exception as error:
  write(args.output/'skill_execution_status.json',{'status':'UNMEASURED','valid_for_model_statistics':False,'error_type':type(error).__name__,'error':str(error),'at':now()});print(str(error),file=sys.stderr);return 2
 print(canonical({'status':'measured','process_score':result['process_score'],'cache_key':result['cache_key'],'origin':result['cache_provenance']['origin']}));return 0


if __name__=='__main__':raise SystemExit(main())
