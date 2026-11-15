"""Source-bound handover observations; no model-selected task reward."""
from pathlib import Path
import argparse
import copy
import datetime
import hashlib
import json
import os
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import uuid
from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def schema(contract,sources=None):
    identifier={'type':'string'}
    if sources is not None:identifier['enum']=[row['id'] for row in sources]
    citation={'type':'object','additionalProperties':False,'required':['source_file_id','line_numbers'],'properties':{'source_file_id':identifier,'line_numbers':{'type':'array','minItems':1,'maxItems':30,'items':{'type':'integer','minimum':1}}}}
    adopted=copy.deepcopy(citation)
    if sources is not None:adopted['properties']['source_file_id']['enum']=[row['id'] for row in sources if row['kind']=='delivered_handover'] or ['no-adopted-handover-document']
    common={'source_citations':{'type':'array','items':citation},'evidence':{'type':'string'},'why':{'type':'string'}}
    ticket={'type':'object','additionalProperties':False,'required':[*contract['ticket_fields'],'selected_actual_command_ids',*common],'properties':{**{key:{'type':['boolean','null']} for key in contract['ticket_fields']},'selected_actual_command_ids':{'type':'array','items':{'type':'string'}},**common}}
    unit={'type':'object','additionalProperties':False,'required':['completion',*common],'properties':{'completion':{'type':['number','null'],'enum':[0,0.5,1,None]},**common}}
    claim={'type':'object','additionalProperties':False,'required':['kind','asserted_value','verdict','adopted_claim_citations',*common],'properties':{'kind':{'type':'string','enum':contract['source_claim_kinds']},'asserted_value':{'type':'string'},'verdict':{'type':'string','enum':['accurate','contradicted','unsupported','unclear']},'adopted_claim_citations':{'type':'array','minItems':1,'items':adopted},**common}}
    return {'type':'object','additionalProperties':False,'required':['tickets','professional','source_claims'],'properties':{'tickets':{'type':'object','additionalProperties':False,'required':contract['ticket_ids'],'properties':{key:ticket for key in contract['ticket_ids']}},'professional':{'type':'object','additionalProperties':False,'required':list(contract['professional_units']),'properties':{key:unit for key in contract['professional_units']}},'source_claims':{'type':'array','items':claim}}}


def collect(artifact,evidence_path):
    sources=[];hashes={};remaining=200_000
    def add(identifier,path,text,kind):
        nonlocal remaining
        lines=text.splitlines(keepends=True)
        allowance=min(30_000,remaining)
        chosen=text[:allowance];remaining-=len(chosen)
        sources.append(dict(id=identifier,path=path,kind=kind,sha256=digest(text),text=chosen,truncated=len(chosen)<len(text)))
    inventory=[]
    for path in sorted(artifact.rglob('*')):
        if not path.is_file() or any(part in ['.godot','__pycache__','.git'] for part in path.relative_to(artifact).parts):continue
        relative=str(path.relative_to(artifact));hashes[relative]=sha(path);inventory.append(dict(path=relative,sha256=hashes[relative],bytes=path.stat().st_size))
        if path.name=='delivery-register.xlsx':
            workbook=load_workbook(path,data_only=True)
            text='\n'.join(sheet.title+' row'+str(index)+': '+json.dumps(list(row),ensure_ascii=False) for sheet in workbook for index,row in enumerate(sheet.iter_rows(values_only=True),1))
            add('delivery-register',relative,text,'delivered_handover')
        elif path.suffix.lower() in ['.gd','.cfg','.godot','.tscn','.md','.txt','.log','.csv','.json','.sha256'] and path.stat().st_size<=500_000:
            add('artifact-'+str(len(sources)),relative,path.read_text(errors='replace'),'project_code' if relative.startswith('project/') else 'delivered_handover')
    add('artifact-inventory','Complete delivered file inventory',json.dumps(dict(scan_complete=True,file_count=len(inventory),actual_files=inventory,inventory_truncated=False),ensure_ascii=False,indent=2),'actual_inventory')
    evidence=read(evidence_path) if evidence_path else {'documents':[],'commands':[]}
    for index,row in enumerate(evidence.get('documents',[])):
        add('external-'+str(index),row['path'],row['text'],'external_history_not_delivered')
    if evidence.get('final_message'):
        add('final-message','actual final handover response',evidence['final_message'],'delivered_handover')
    command_ids={row['id'] for row in evidence.get('commands',[])}
    assert len(command_ids)==len(evidence.get('commands',[]))
    public=[dict(id=row['id'],path=row['path'],kind=row['kind'],sha256=row['sha256'],truncated=row['truncated'],line_indexed_text=''.join(str(index)+': '+line for index,line in enumerate(row['text'].splitlines(keepends=True),1))) for row in sources]
    public_commands=[{key:value for key,value in row.items() if key!='source_call_ids'} for row in evidence.get('commands',[])]
    return sources,dict(actual_files=inventory,source_documents=public,actual_execution_commands=public_commands),hashes,command_ids,evidence


def validate(reply,contract,sources,command_ids):
    def exact(value,keys):return isinstance(value,dict) and set(value)==set(keys)
    assert exact(reply,['tickets','professional','source_claims']),'Top-level schema mismatch'
    assert exact(reply['tickets'],contract['ticket_ids']) and exact(reply['professional'],contract['professional_units']),'Unit IDs mismatch'
    source_ids={row['id']:row for row in sources}
    def citations(row,field='source_citations'):
        assert isinstance(row[field],list) and row[field],'Actual source citation required'
        quotes=[]
        for citation in row[field]:
            assert exact(citation,['source_file_id','line_numbers'])
            source=source_ids[citation['source_file_id']];lines=source['text'].splitlines(keepends=True)
            numbers=citation['line_numbers']
            assert isinstance(numbers,list) and 1<=len(numbers)<=30 and len(set(numbers))==len(numbers)
            assert all(type(number) is int and 1<=number<=len(lines) for number in numbers),'Invented citation line bounds'
            quotes.append(dict(citation,source_sha256=source['sha256'],quoted_lines=[dict(line_number=number,text=lines[number-1]) for number in numbers]))
        assert all(isinstance(row[key],str) and row[key].strip() for key in ['evidence','why'])
        row['materialized_'+field]=quotes
    result=copy.deepcopy(reply)
    uncertain=False
    for key,row in result['tickets'].items():
        assert exact(row,[*contract['ticket_fields'],'selected_actual_command_ids','source_citations','evidence','why'])
        for field in contract['ticket_fields']:
            assert row[field] is None or type(row[field]) is bool
            uncertain=uncertain or row[field] is None
        assert isinstance(row['selected_actual_command_ids'],list) and len(set(row['selected_actual_command_ids']))==len(row['selected_actual_command_ids'])
        assert all(value in command_ids for value in row['selected_actual_command_ids']),'Invented historical command'
        # Delivered logs and traces may establish correspondence without private
        # author-history command identifiers.
        citations(row)
    for key,row in result['professional'].items():
        assert exact(row,['completion','source_citations','evidence','why']) and row['completion'] in [None,0,.5,1]
        uncertain=uncertain or row['completion'] is None
        citations(row)
    seen=set()
    for row in result['source_claims']:
        assert exact(row,['kind','asserted_value','verdict','adopted_claim_citations','source_citations','evidence','why'])
        assert row['kind'] in contract['source_claim_kinds'] and row['verdict'] in ['accurate','contradicted','unsupported','unclear']
        assert isinstance(row['asserted_value'],str)
        key=(row['kind'],row['asserted_value'].strip().lower())
        assert key not in seen,'Repeated fact must be grouped, not charged again'
        seen.add(key);citations(row);citations(row,'adopted_claim_citations')
        assert all(source_ids[value['source_file_id']]['kind']=='delivered_handover' for value in row['adopted_claim_citations']),'Source claims require an actual adopted handover assertion'
        if row['verdict']=='contradicted' and row['kind'] in ['original_png_count','source_fps']:
            assert any(source_ids[value['source_file_id']]['kind'] in ['authority','actual_inventory'] for value in row['source_citations']),'Contradicted source-origin claims need actual authority or inventory'
        # An unresolved optional factual claim loses its own factual-credit
        # share during settlement; it does not make the complete delivery
        # unmeasurable when the cited artifact and all required units are read.
    result['status']='needs_review' if uncertain else 'measured'
    return result


def parse_response(raw):
    data=json.loads(raw)
    messages=[row for row in data.get('output',[]) if row.get('type')=='message']
    assert messages,'No final response message'
    text=''.join(row['text'] for row in messages[-1]['content'] if row.get('type')=='output_text')
    return data,json.loads(text)


def run(args):
    artifact=Path(args.artifact).resolve();output=Path(args.output).resolve();cache=Path(args.cache_dir).resolve()
    assert not output.is_relative_to(artifact) and not cache.is_relative_to(artifact)
    output.mkdir(parents=True,exist_ok=True)
    contract=read(HERE/'contract.json');settings=read(HERE/'settings.json');settings['model']=os.environ.get('LLM_JUDGE_MODEL',settings['model'])
    sources,packet,hashes,command_ids,evidence=collect(artifact,args.evidence)
    authority=read(HERE/'authority.json')
    for index,row in enumerate(authority['documents']):
        text=row['text'];sources.append(dict(id='authority-'+str(index),path=row['path'],kind='authority',sha256=digest(text),text=text,truncated=False))
        packet['source_documents'].append(dict(id='authority-'+str(index),path=row['path'],kind='authority',sha256=digest(text),truncated=False,line_indexed_text=''.join(str(number)+': '+line for number,line in enumerate(text.splitlines(keepends=True),1))))
    original=authority.get('original_project_files',{})
    if original:
        comparison=[dict(original_path=path,original_sha256=value,delivered_sha256=hashes.get('project/'+path),same_bytes=hashes.get('project/'+path)==value) for path,value in original.items()]
        pngs=[row for row in comparison if row['original_path'].lower().endswith('.png')]
        summary=dict(original_png_count=len(pngs),same_byte_png_count=sum(row['same_bytes'] for row in pngs),missing_or_changed_pngs=[row['original_path'] for row in pngs if not row['same_bytes']],source='Actual original supplied project hashes compared mechanically with this complete delivered inventory; no actor claim supplies the result.')
        text=json.dumps(summary,ensure_ascii=False)+'\n'+'\n'.join(json.dumps(row,ensure_ascii=False) for row in comparison)
        identity=dict(id='actual-original-file-comparison',path='Mechanically measured original/delivered file identity comparison',kind='actual_inventory',sha256=digest(text),text=text,truncated=False)
        sources.append(identity)
        packet['source_documents'].append({key:value for key,value in identity.items() if key!='text'}|dict(line_indexed_text=''.join(str(number)+': '+line for number,line in enumerate(text.splitlines(keepends=True),1))))
    packet.update(criteria=contract,canonical_facts=authority['canonical_facts'])
    names=['judge.py','contract.json','prompt.md','settings.json','response.schema.json','authority.json']
    runtime={name:sha(HERE/name) for name in names}
    binding=dict(version=contract['version'],artifact_files=hashes,evidence_sha256=digest(evidence),runtime=runtime,settings=settings,packet_sha256=digest(packet),response_protocol='Last Responses message, concatenated output_text parts in that message; no selection by score.')
    key=digest(binding);record=None;started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        if args.mode=='replay':
            call_id=read(cache/key/'selected.json')['call_id'];assert call_id and all(c in '0123456789abcdefghijklmnopqrstuvwxyz-' for c in call_id)
            record=cache/key/call_id;request=read(record/'request.json');verification=read(record/'validation.json')
            assert verification['valid'] and digest(request['binding'])==key
            assert sha(record/'request.json')==verification['request_sha256'] and sha(record/'response.json')==verification['response_sha256']
            data,reply=parse_response((record/'response.json').read_text());decision=validate(reply,contract,sources,command_ids)
            assert decision==read(record/'decision.json'),'Replay decision drift'
        else:
            assert args.refresh,'Fresh requires --refresh'
            base=os.environ['LLM_JUDGE_BASE_URL'].rstrip('/');api_key=os.environ['LLM_JUDGE_API_KEY']
            if not base.endswith('/v1'):base+='/v1'
            endpoint=base+'/responses';url=urllib.parse.urlsplit(endpoint)
            assert url.scheme in ['http','https'] and not url.username and not url.password and not url.query
            call_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex;record=cache/key/call_id;record.mkdir(parents=True)
            body=dict(model=settings['model'],store=False,reasoning={'effort':settings['reasoning_effort']},max_output_tokens=settings['max_output_tokens'],instructions=(HERE/'prompt.md').read_text(),input=[dict(role='user',content=[dict(type='input_text',text=json.dumps(packet,ensure_ascii=False))])],text={'format':{'type':'json_schema','name':'godot_handover_evidence','strict':True,'schema':schema(contract,sources)}})
            save(record/'request.json',dict(binding=binding,endpoint=endpoint,body=body))
            wire=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+api_key})
            try:
                with urllib.request.urlopen(wire,timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS',settings['timeout_seconds']))) as response:status,raw=response.status,response.read().decode()
            except urllib.error.HTTPError as error:status,raw=error.code,error.read().decode()
            raw=raw.replace(api_key,'[REDACTED]');(record/'response.json').write_text(raw)
            assert 200<=status<300,'Provider HTTP '+str(status)+'; raw wire retained'
            data,reply=parse_response(raw);decision=validate(reply,contract,sources,command_ids)
            assert all(sha(HERE/name)==value for name,value in runtime.items())
            assert collect(artifact,args.evidence)[2]==hashes,'Artifact changed during call'
            save(record/'decision.json',decision);save(record/'validation.json',dict(valid=True,started=started,finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),request_sha256=sha(record/'request.json'),response_sha256=sha(record/'response.json'),returned_model=data.get('model'),response_id=data.get('id'),usage=data.get('usage'),no_model_reward=True))
            save(cache/key/'selected.json',dict(call_id=call_id))
        result=dict(decision,binding=binding,cache_key=key,call_id=call_id,record=str(record),mode=args.mode,returned_model=data.get('model'),provider_call_performed=args.mode=='fresh',task_reward=None)
    except Exception as error:
        if record and args.mode=='fresh':save(record/'validation.json',dict(valid=False,started=started,error=str(error)))
        result=dict(status='judge_error',binding=binding,error=str(error),task_reward=None)
    save(output/'llm_judge_result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['fresh','replay'],required=True);parser.add_argument('--refresh',action='store_true')
    for name in ['artifact','output','cache-dir']:parser.add_argument('--'+name,required=True)
    parser.add_argument('--evidence')
    args=parser.parse_args()
    try:result=run(args)
    except Exception as error:
        result=dict(status='judge_error',error=str(error),task_reward=None);save(Path(args.output)/'llm_judge_result.json',result)
    print(json.dumps(dict(status=result['status'],error=result.get('error'),cache_key=result.get('cache_key'))))
    raise SystemExit(0 if result['status']=='measured' else 2)


if __name__=='__main__':main()
