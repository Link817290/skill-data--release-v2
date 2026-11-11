"""Portable read-only semantic judgment with bound fresh and replay records."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import fcntl
import urllib.request
import urllib.parse

import openpyxl

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'runtime'))
from official_transport import official_call


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n')


def register_fresh(cache,key,entry,artifact):
    with (cache/'manifest.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=cache/'manifest.json'
        manifest=json.loads(path.read_text()) if path.exists() else {'schema_version':'mx6-semantic-cache-1','entries':{}}
        binding={'entry':str(entry.relative_to(cache)),'artifact_sha256':sha(artifact),
            'request_sha256':sha(entry/'request.json'),'response_sha256':sha(entry/'response.json'),
            'decision_sha256':sha(entry/'decision.json'),'validation_sha256':sha(entry/'validation.json')}
        manifest.setdefault('fresh_history',[]).append({'context_sha256':key,**binding})
        if key not in manifest['entries']:manifest['entries'][key]=binding
        write(path,manifest)


def stable(value):
    if isinstance(value,float):
        rounded=round(value,8)
        return 0.0 if rounded==0 else rounded
    if isinstance(value,list):return [stable(item) for item in value]
    if isinstance(value,dict):return {key:stable(value[key]) for key in sorted(value)}
    return value


def grouped(values):
    groups={}
    for value in values:
        before=stable(value['before']);after=stable(value['after'])
        key=(value['sheet'],canonical(before),canonical(after))
        if key not in groups:
            groups[key]={'sheet':value['sheet'],'cells':[],'before':before,'after':after}
        groups[key]['cells'].append(value['cell'])
    rows=[]
    for index,key in enumerate(sorted(groups)):
        row=groups[key];row['id']='O'+str(index).zfill(4);row['cells'].sort();rows.append(row)
    return rows


def request_body(artifact,observations):
    source=json.loads(Path(observations).read_text())
    if source['phase']!='observed' or not source['source_unchanged'] or len(source['scenarios'])!=44:
        raise RuntimeError('Native diagnostic evidence incomplete')
    if source['candidate_sha256']!=sha(artifact):raise RuntimeError('Native artifact binding mismatch')
    book=openpyxl.load_workbook(artifact)
    labels=[]
    for sheet in book:
        for cells in sheet.iter_rows(min_row=1,max_row=4):
            for cell in cells:
                if cell.data_type!='f' and isinstance(cell.value,str):
                    labels.append({'sheet':sheet.title,'cell':cell.coordinate,'text':cell.value})
    for cells in book.worksheets[8].iter_rows(min_row=5,max_row=15):
        for cell in cells:
            if cell.data_type!='f' and isinstance(cell.value,str):
                labels.append({'sheet':book.worksheets[8].title,'cell':cell.coordinate,'text':cell.value})
    book.close()
    payload={'actual_static_worksheet_and_control_labels':labels,
        'baseline_nonempty_formula_text_and_controls':stable(source['baseline_diagnostic_values']),
        'scenarios':[{'id':s['id'],'changes':stable(s['changes']),'outputs':grouped(s['changed_outputs'])} for s in source['scenarios']]}
    settings=json.loads((HERE/'settings.json').read_text())
    schema=json.loads((HERE/'response.schema.json').read_text())
    body={'model':settings['model'],'input':[{'role':'user','content':[
        {'type':'input_text','text':(HERE/'prompt.md').read_text()},
        {'type':'input_text','text':json.dumps(payload,ensure_ascii=True)}]}],
        'reasoning':{'effort':settings['reasoning_effort']},'store':False,'stream':False,
        'text':{'format':{'type':'json_schema','name':'mx6_visible_input_diagnoses','strict':True,'schema':schema}}}
    return body,payload,settings


def validate(decisions,payload):
    rows=decisions['decisions'];expected={s['id']:s for s in payload['scenarios']}
    if len(rows)!=44 or {r['scenario_id'] for r in rows}!=set(expected):raise RuntimeError('Scenario schema mismatch')
    for row in rows:
        if row['status']!='measured' or row['completion'] not in (0,1):raise RuntimeError('Unresolved semantic evidence')
        outputs={o['id']:o for o in expected[row['scenario_id']]['outputs']}
        if row['completion']==1 and not row['evidence']:raise RuntimeError('Missing positive evidence')
        for cited in row['evidence']:
            actual=outputs.get(cited['output_id']);numeric=False
            if actual is not None and isinstance(actual['after'],(int,float)):
                try:numeric=abs(float(cited['quote'])-actual['after'])<1e-12
                except (ValueError,TypeError):pass
            if actual is None or cited['quote']!=str(actual['after']) and not numeric:
                raise RuntimeError('Semantic quote is not bound to actual output')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',required=True,choices=['auto','fresh','replay'])
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--artifact',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--cache-dir',required=True)
    parser.add_argument('--golden-replay-dir',required=True)
    parser.add_argument('--observations')
    parser.add_argument('--material',default=str(HERE.parent/'material.xlsx'))
    args=parser.parse_args()
    artifact=Path(args.artifact).resolve();output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    observations=Path(args.observations).resolve() if args.observations else output/'native/diagnostics.json'
    if not args.observations:
        command=[sys.executable,'-B',str(HERE.parent/'runtime/measure.py'),'--artifact',str(artifact),
                 '--material',str(Path(args.material).resolve()),'--output',str(observations.parent),'--family','diagnostics']
        done=subprocess.run(command,capture_output=True,text=True)
        write(output/'native-execution.json',{'command':command,'exit_code':done.returncode,'stdout':done.stdout,'stderr':done.stderr})
        if done.returncode:raise RuntimeError('Native extraction failed; no score assigned')
    body,payload,settings=request_body(artifact,observations)
    cache=Path(args.cache_dir).resolve();key=digest({'body':body,'artifact_sha256':sha(artifact)})
    mode=args.mode;replay_cache=cache
    if mode=='auto':
        golden=Path(args.golden_replay_dir).resolve();manifest_path=golden/'manifest.json'
        manifest=json.loads(manifest_path.read_text()) if manifest_path.is_file() else {'entries':{}}
        binding=manifest['entries'].get(key)
        if binding and binding.get('qualification_status')=='qualified_gpt_responses':mode='replay';replay_cache=golden
        else:mode='fresh'
    if mode=='replay':
        manifest=json.loads((replay_cache/'manifest.json').read_text())
        binding=manifest['entries'].get(key)
        if not binding:raise RuntimeError('Trusted semantic cache miss; fresh judgment required')
        if binding.get('qualification_status')!='qualified_gpt_responses':
            raise RuntimeError('Trusted semantic replay is pending a qualified GPT Responses replacement')
        entry=replay_cache/binding['entry']
        if sha(entry/'request.json')!=binding['request_sha256'] or sha(entry/'decision.json')!=binding['decision_sha256']:
            raise RuntimeError('Trusted cache file binding changed')
        request=json.loads((entry/'request.json').read_text())
        if digest({'body':request['body'],'artifact_sha256':request['artifact_sha256']})!=key or request['artifact_sha256']!=sha(artifact):
            raise RuntimeError('Trusted artifact/context binding mismatch')
        decisions=json.loads((entry/'decision.json').read_text())
        validate(decisions,payload)
    else:
        endpoint=os.environ.get('LLM_JUDGE_BASE_URL');api_key=os.environ.get('LLM_JUDGE_API_KEY')
        if not endpoint or not api_key:raise RuntimeError('Fresh judgment requires verifier-only endpoint and key environment variables')
        configured_model=os.environ.get('LLM_JUDGE_MODEL',settings['model'])
        if configured_model!='gpt-5.6-sol' or settings['model']!='gpt-5.6-sol':
            raise RuntimeError('Only the qualified gpt-5.6-sol judge is accepted')
        protocol='responses'
        fresh_context=digest({'base_context':key,'protocol':protocol,'model':configured_model,
            'endpoint_origin':urllib.parse.urlparse(endpoint).netloc+urllib.parse.urlparse(endpoint).path})
        key=digest({'fresh_context':fresh_context,'artifact_sha256':sha(artifact)})
        entry=cache/'fresh'/key/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
        entry.mkdir(parents=True,exist_ok=False)
        write(entry/'request.json',{'body':body,'artifact_sha256':sha(artifact),
            'observation_sha256':sha(observations),'prompt_sha256':sha(HERE/'prompt.md')})
        try:
            timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS',settings['timeout_sec']))
            if timeout < 60:raise RuntimeError('LLM_JUDGE_TIMEOUT_SECONDS must be at least 60')
            provider=official_call(body,entry,endpoint,api_key,timeout)
            if provider.get('status')!='completed' or provider.get('model')!=configured_model:
                raise RuntimeError('Incomplete or mismatched Responses judge result')
            if api_key in canonical(provider):raise RuntimeError('Credential echo withheld')
            write(entry/'response.json',provider)
            text='\n'.join(c['text'] for item in provider.get('output',[]) if item.get('type')=='message'
                           for c in item.get('content',[]) if c.get('type')=='output_text')
            decisions=json.loads(text);validate(decisions,payload)
            write(entry/'decision.json',decisions)
            write(entry/'validation.json',{'status':'qualified','atomic_binary':True,'all_44_ids':True,'quotes_bound':True,
                'response_sha256':sha(entry/'response.json'),'returned_model':provider.get('model'),'response_id':provider.get('id')})
            register_fresh(cache,key,entry,artifact)
        except Exception as error:
            write(entry/'failure.json',{'status':'judge_failure','error_type':type(error).__name__,'candidate_score_assigned':False})
            raise
    result={'judge_version':'mx6-visible-input-diagnoses-1','status':'measured','artifact_sha256':sha(artifact),
        'context_sha256':key,'mode':mode,'cache_entry':str(entry),'decisions':decisions['decisions'],
            'request_sha256':sha(entry/'request.json'),'decision_sha256':sha(entry/'decision.json')}
    write(output/'llm_judge_result.json',result)
    write(output/'decision.json',decisions)
    print(json.dumps({'status':'measured','decision_count':44,'mode':mode}),flush=True)


if __name__=='__main__':main()
