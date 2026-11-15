"""Fresh/replay source-bound retained verification observations; no reward selection."""
from pathlib import Path
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import judge as source

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def schema(sources):
    citation={'type':'object','additionalProperties':False,'required':['source_file_id','line_numbers'],'properties':{'source_file_id':{'type':'string','enum':[row['id'] for row in sources]},'line_numbers':{'type':'array','minItems':1,'maxItems':30,'items':{'type':'integer','minimum':1}}}}
    properties={'completion':{'type':['number','null'],'enum':[0,.5,1,None]},'retained_citations':{'type':'array','items':citation},'support_citations':{'type':'array','items':citation},'actual_command_ids':{'type':'array','items':{'type':'string'}},'evidence':{'type':'string'},'why':{'type':'string'}}
    return dict(type='object',additionalProperties=False,required=list(properties),properties=properties)


def validate(value,sources,commands):
    assert isinstance(value,dict) and set(value)==set(schema(sources)['properties'])
    assert value['completion'] in [None,0,.5,1]
    ids={row['id']:row for row in sources}
    materialized={}
    for field in ['retained_citations','support_citations']:
        assert isinstance(value[field],list) and (value[field] or (field=='retained_citations' and value['completion']==0))
        quotes=[]
        for citation in value[field]:
            assert set(citation)=={'source_file_id','line_numbers'}
            row=ids[citation['source_file_id']];lines=row['text'].splitlines(keepends=True);numbers=citation['line_numbers']
            assert 1<=len(numbers)<=30 and len(set(numbers))==len(numbers)
            assert all(type(number) is int and 1<=number<=len(lines) for number in numbers)
            if field=='retained_citations':assert row['kind'] not in ['external_history_not_delivered','authority'],'Private history or original specification is not automatically a retained observation'
            quotes.append(dict(citation,source_sha256=row['sha256'],quoted_lines=[dict(line_number=number,text=lines[number-1]) for number in numbers]))
        materialized[field]=quotes
    assert isinstance(value['actual_command_ids'],list) and set(value['actual_command_ids'])<=commands
    assert all(isinstance(value[key],str) and value[key].strip() for key in ['evidence','why'])
    # Retained delivered traces can establish receiver evidence even when no
    # private author-history command identifiers are supplied.
    return dict(value,materialized_citations=materialized,status='needs_review' if value['completion'] is None else 'measured')


def run(args):
    artifact=Path(args.artifact).resolve();out=Path(args.output).resolve();cache=Path(args.cache_dir).resolve()
    assert not out.is_relative_to(artifact) and not cache.is_relative_to(artifact)
    out.mkdir(parents=True,exist_ok=True)
    sources,packet,hashes,commands,evidence=source.collect(artifact,args.evidence)
    authority=source.read(BASE/'authority.json')
    for index,row in enumerate(authority['documents']):
        text=row['text'];entry=dict(id='authority-'+str(index),path=row['path'],kind='authority',sha256=source.digest(text),text=text,truncated=False);sources.append(entry)
        packet['source_documents'].append({key:value for key,value in entry.items() if key!='text'}|dict(line_indexed_text=''.join(str(number)+': '+line for number,line in enumerate(text.splitlines(keepends=True),1))))
    packet['criteria']=source.read(HERE/'contract.json')
    settings=source.read(BASE/'settings.json');settings['model']=os.environ.get('LLM_JUDGE_MODEL',settings['model']);settings['max_output_tokens']=8000
    runtime={name:source.sha(HERE/name) for name in ['judge.py','contract.json','prompt.md']}
    base_runtime=source.read(BASE/'manifest.json')['runtime_files']
    assert all(source.sha(BASE/name)==value for name,value in base_runtime.items())
    binding=dict(version=packet['criteria']['version'],artifact_files=hashes,evidence_sha256=source.digest(evidence),runtime=runtime,base_runtime=base_runtime,settings=settings,packet_sha256=source.digest(packet),response_protocol='Last Responses message output_text; no selection by reward.')
    key=source.digest(binding);record=None;started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        if args.mode=='replay':
            call_id=source.read(cache/key/'selected.json')['call_id'];assert call_id and all(character in '0123456789abcdefghijklmnopqrstuvwxyz-' for character in call_id);record=cache/key/call_id
            receipt=source.read(record/'validation.json');assert receipt['valid']
            assert receipt['request_sha256']==source.sha(record/'request.json') and receipt['response_sha256']==source.sha(record/'response.json')
            request=source.read(record/'request.json')
            response,reply=source.parse_response((record/'response.json').read_text())
            decision=source.read(record/'decision.json')
        else:
            assert args.refresh
            base=os.environ['LLM_JUDGE_BASE_URL'].rstrip('/');credential=os.environ['LLM_JUDGE_API_KEY']
            if not base.endswith('/v1'):base+='/v1'
            endpoint=base+'/responses';url=urllib.parse.urlsplit(endpoint)
            assert url.scheme in ['http','https'] and not url.username and not url.password and not url.query
            call_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex;record=cache/key/call_id;record.mkdir(parents=True)
            body=dict(model=settings['model'],store=False,reasoning=dict(effort=settings['reasoning_effort']),max_output_tokens=settings['max_output_tokens'],instructions=(HERE/'prompt.md').read_text(),input=[dict(role='user',content=[dict(type='input_text',text=json.dumps(packet,ensure_ascii=False))])],text=dict(format=dict(type='json_schema',name='godot_retained_verification',strict=True,schema=schema(sources))))
            source.save(record/'request.json',dict(binding=binding,endpoint=endpoint,body=body))
            request=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+credential})
            try:
                with urllib.request.urlopen(request,timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS',settings['timeout_seconds']))) as response:status,raw=response.status,response.read().decode()
            except urllib.error.HTTPError as error:status,raw=error.code,error.read().decode()
            raw=raw.replace(credential,'[REDACTED]');(record/'response.json').write_text(raw);assert 200<=status<300,'Provider HTTP '+str(status)
            response,reply=source.parse_response(raw);decision=validate(reply,sources,commands)
            assert source.collect(artifact,args.evidence)[2]==hashes
            assert all(source.sha(HERE/name)==value for name,value in runtime.items())
            assert all(source.sha(BASE/name)==value for name,value in base_runtime.items())
            source.save(record/'decision.json',decision)
            source.save(record/'validation.json',dict(valid=True,started=started,finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),request_sha256=source.sha(record/'request.json'),response_sha256=source.sha(record/'response.json'),returned_model=response.get('model'),response_id=response.get('id'),usage=response.get('usage')))
            source.save(cache/key/'selected.json',dict(call_id=call_id))
        result=dict(decision,binding=binding,cache_key=key,call_id=call_id,mode=args.mode,provider_call_performed=args.mode=='fresh',task_reward=None)
    except Exception as error:
        if record and args.mode=='fresh':source.save(record/'validation.json',dict(valid=False,error=str(error),started=started))
        result=dict(status='judge_error',error=str(error),binding=binding,task_reward=None)
    source.save(out/'llm_judge_result.json',result);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['fresh','replay'],required=True);parser.add_argument('--refresh',action='store_true')
    for key in ['artifact','evidence','output','cache-dir']:parser.add_argument('--'+key,required=True)
    args=parser.parse_args();result=run(args);print(json.dumps(dict(status=result['status'],completion=result.get('completion'),error=result.get('error'))));raise SystemExit(0 if result['status']=='measured' else 2)


if __name__=='__main__':main()
