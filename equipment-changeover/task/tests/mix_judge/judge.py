"""Text-only, source-bound semantic comparison. Never launches a solving agent."""
import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import fitz
from docx import Document
import csv

HERE = Path(__file__).resolve().parent
TASK_ROOT = HERE.parents[1]
ROOT = TASK_ROOT.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_units(path, prefix):
    units = []
    if path.suffix.lower() == '.pdf':
        with fitz.open(path) as doc:
            for n, page in enumerate(doc, 1):
                for b, block in enumerate(page.get_text('blocks'), 1):
                    if isinstance(block[4], str) and block[4].strip():
                        units.append(dict(id=f'{prefix}-P{n}-B{b}', text=block[4].strip()))
    elif path.suffix.lower() == '.docx':
        doc = Document(path)
        units.extend(dict(id=f'{prefix}-P{i}', text=p.text) for i, p in enumerate(doc.paragraphs) if p.text.strip())
        for t, table in enumerate(doc.tables):
            units.extend(dict(id=f'{prefix}-T{t}-R{r}', text=' | '.join(c.text for c in row.cells)) for r, row in enumerate(table.rows))
    else:
        raise ValueError('Report must be PDF or Word; adapt other equivalent evidence explicitly')
    if not units:
        raise ValueError('No report text extracted; OCR or another verified extraction is required')
    return units



def extract(path,prefix):
    if path.suffix=='.docx':return report_units(path,prefix)
    if path.suffix=='.pdf':return report_units(path,prefix)
    if path.suffix=='.xlsx':
        from openpyxl import load_workbook
        w=load_workbook(path,data_only=False);units=[]
        for sn,s in enumerate(w,1):
            for rn,row in enumerate(s.iter_rows(values_only=True),1):
                if any(v is not None for v in row):units.append(dict(id=f'{prefix}-S{sn}-R{rn}',text=s.title+' | '+' | '.join('' if v is None else str(v) for v in row)))
        return units
    if path.suffix in ['.csv','.txt','.json']:
        return [dict(id=f'{prefix}-L{i}',text=x) for i,x in enumerate(path.read_text(encoding='utf8').splitlines(),1) if x.strip()]
    return []

def build_evidence(submission,input_dir):
    contract=json.loads((HERE/'contract.json').read_text(encoding='utf8'))
    evidence=dict(candidate=[],workbook_sample=[],golden_meaning=[],source_materials=[],verified_facts=[])
    hashes={}
    for group,folder,prefix in [('candidate',submission,'C'),('golden_meaning',ROOT/'golden','G')]:
        for i,name in enumerate(contract['outputs'],1):
            p=folder/name
            evidence[group]+=extract(p,f'{prefix}{i}')
            hashes[group+'/'+name]=sha(p)
    for i,p in enumerate(sorted(input_dir.rglob('*')),1):
        if p.is_file():
            units=extract(p,f'S{i}')
            if units:evidence['source_materials']+=units;hashes['source/'+p.relative_to(input_dir).as_posix()]=sha(p)
    fp=TASK_ROOT/'tests/reference/facts.json'
    evidence['verified_facts']=[dict(id='F1',text=fp.read_text(encoding='utf8'))];hashes['facts']=sha(fp)
    evidence['scope']='All supplied business document text and table rows. No visual assessment. Source evidence takes precedence over reference.'
    return evidence,hashes

def response_schema(evidence, contract):
    candidate_ids = [r['id'] for group in ['candidate', 'workbook_sample'] for r in evidence[group]]
    reference_ids = [r['id'] for group in ['golden_meaning', 'source_materials', 'verified_facts'] for r in evidence[group]]
    def ids(values):
        return dict(type='array', items=dict(type='string', enum=values), minItems=1, maxItems=2)
    properties = {}
    for criterion in contract['criteria']:
        properties[criterion['id']] = dict(type='object', additionalProperties=False,
            properties=dict(score=dict(type='number', enum=[0, 1]), reason=dict(type='string'),
                candidate_ids=ids(candidate_ids), reference_ids=ids(reference_ids)),
            required=['score', 'reason', 'candidate_ids', 'reference_ids'])
    return dict(type='object', additionalProperties=False,
        properties=dict(reference_conflict=dict(type='boolean'), criteria=dict(type='object',
            additionalProperties=False, properties=properties, required=list(properties)),
            notes=dict(type='array', items=dict(type='string'))),
        required=['reference_conflict', 'criteria', 'notes'])


def parse_response(envelope, evidence, contract):
    if envelope.get('status') != 'completed': raise ValueError('Incomplete semantic measurement')
    answer=''.join(c.get('text','') for o in envelope.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text').strip()
    if answer.startswith('```'):answer=answer.split('\n',1)[1].rsplit('```',1)[0]
    result=json.loads(answer)
    if type(result.get('reference_conflict')) is not bool:raise ValueError('Reference conflict must be Boolean')
    decisions=result.get('criteria')
    expected={c['id']:c for c in contract['criteria']}
    if not isinstance(decisions,dict) or set(decisions)!=set(expected):raise ValueError('Criteria coverage incomplete')
    units={r['id']:r['text'] for group in ['candidate','workbook_sample','golden_meaning','source_materials','verified_facts'] for r in evidence[group]}
    candidate_ids={r['id'] for group in ['candidate','workbook_sample'] for r in evidence[group]}
    reference_ids=set(units)-candidate_ids
    rows=[]
    for identifier in expected:
        row=decisions[identifier]
        if type(row.get('score')) not in (int,float) or row['score'] not in [0,1]:raise ValueError('Invalid criterion score')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():raise ValueError('Reason missing')
        for key,allowed in [('candidate_ids',candidate_ids),('reference_ids',reference_ids)]:
            selected=row.get(key)
            if not isinstance(selected,list) or not 1<=len(selected)<=2 or any(type(x) is not str or x not in allowed for x in selected):
                raise ValueError('Invalid evidence-unit selection: '+identifier+'/'+key)
            if len(set(selected))!=len(selected):raise ValueError('Duplicate evidence-unit selection')
        citations=[dict(id=key,quote=units[key],quote_origin='runtime_exact_evidence_unit')
                   for key in row['candidate_ids']+row['reference_ids']]
        rows.append(dict(id=identifier,score=row['score'],reason=row['reason'],evidence=citations))
    passed=all(r['score']==1 for r in rows) and not result['reference_conflict']
    result['criteria']=rows
    result['passed']=passed
    result['evidence_binding']='model_selected_ids_runtime_exact_full_unit_text_v1'
    result['semantic_score']=None if result['reference_conflict'] else round(sum(expected[r['id']]['weight']*r['score'] for r in rows),6)
    result['measurement_status']='reference_conflict_requires_review' if result['reference_conflict'] else 'completed'
    return result


def merge_results(parts, contract):
    expected={row['id']:row for row in contract['criteria']}
    rows=[row for part in parts for row in part['criteria']]
    if len(rows)!=len(expected) or {row['id'] for row in rows}!=set(expected):
        raise ValueError('Merged criteria coverage incomplete')
    conflict=any(part['reference_conflict'] for part in parts)
    return {
        'reference_conflict':conflict,
        'criteria':rows,
        'notes':[note for part in parts for note in part.get('notes',[])],
        'passed':not conflict and all(row['score']==1 for row in rows),
        'evidence_binding':'model_selected_ids_runtime_exact_full_unit_text_v1',
        'semantic_score':None if conflict else round(sum(expected[row['id']]['weight']*row['score'] for row in rows),6),
        'measurement_status':'reference_conflict_requires_review' if conflict else 'completed',
    }


def call_judge(url, key, raw, timeout):
    last_error=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,data=raw,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as stream:
                response=stream.read()
            envelope=json.loads(response)
            if envelope.get('status')!='completed':raise ValueError('Judge response was incomplete')
            return response
        except (urllib.error.URLError,TimeoutError,ValueError,json.JSONDecodeError) as error:
            last_error=error
            if attempt<2:time.sleep(attempt+1)
    raise RuntimeError('Semantic judge unavailable after three attempts: '+str(last_error))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--submission-dir',type=Path,required=True)
    parser.add_argument('--input',type=Path,default=TASK_ROOT/'environment/workspace/input')
    parser.add_argument('--facts',type=Path,default=TASK_ROOT/'tests/reference')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--replay',type=Path)
    args=parser.parse_args()
    contract=json.loads((HERE/'contract.json').read_text(encoding='utf-8'))
    settings=json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
    evidence,hashes=build_evidence(args.submission_dir,args.input)
    prompt=(HERE/'prompt.md').read_text(encoding='utf-8')
    size=int(settings.get('criteria_per_batch',8))
    batches=[contract['criteria'][i:i+size] for i in range(0,len(contract['criteria']),size)]
    bodies=[]
    for index,criteria_batch in enumerate(batches,1):
        batch_contract=dict(contract,criteria=criteria_batch)
        text=prompt+'\nCriteria:\n'+json.dumps(criteria_batch,ensure_ascii=False)+'\nEvidence:\n'+json.dumps(evidence,ensure_ascii=False)
        body=dict(model=os.environ.get('LLM_JUDGE_MODEL',settings['model']),store=False,stream=False,
                  reasoning={'effort':settings.get('reasoning_effort','low')},
                  max_output_tokens=settings['max_output_tokens'],input=[dict(role='user',content=[dict(type='input_text',text=text)])])
        body['text']={'format':{'type':'json_schema','name':f'equipment_changeover_semantic_review_{index:02d}','strict':True,
                                'schema':response_schema(evidence,batch_contract)}}
        bodies.append(body)
    args.out.mkdir(parents=True,exist_ok=True)
    if list(args.out.glob('response-*.json')) and not args.replay:raise ValueError('Output already contains a response; choose a new output folder')
    raw_batches=[json.dumps(body,ensure_ascii=False).encode('utf-8') for body in bodies]
    raw=json.dumps({'batches':bodies},ensure_ascii=False).encode('utf-8')
    request_sha=hashlib.sha256(raw).hexdigest()
    (args.out/'request.json').write_bytes(raw)
    (args.out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.out/'manifest.json').write_text(json.dumps(dict(artifact_hashes=hashes,request_sha256=request_sha,
        batch_request_sha256=[hashlib.sha256(item).hexdigest() for item in raw_batches],batch_count=len(batches),
        rollout_executed=False,visual_input=False,contract_sha256=sha(HERE/'contract.json')),ensure_ascii=False,indent=2),encoding='utf-8')
    start=time.time()
    if not args.replay and os.environ.get('LLM_JUDGE_MODE') == 'replay':
        candidate=HERE/'replay'/request_sha
        if not candidate.is_dir():raise ValueError('No exact request-bound packaged replay')
        args.replay=candidate
    responses=[]
    if args.replay:
        replay_dir=args.replay if args.replay.is_dir() else args.replay.parent
        binding=replay_dir/'binding.json'
        prior_manifest=json.loads(binding.read_text(encoding='utf-8')) if binding.is_file() else json.loads((replay_dir/'manifest.json').read_text(encoding='utf-8'))
        if prior_manifest.get('request_sha256')!=request_sha:
            raise ValueError('Cached response belongs to a different request; run a fresh review')
        if prior_manifest.get('artifact_hashes')!=hashes:
            raise ValueError('Cached response belongs to different artifact bytes; run a fresh review')
        if args.out.resolve()==replay_dir.resolve():
            raise ValueError('Replay must not overwrite its archived source evidence')
        for index in range(1,len(batches)+1):
            path=replay_dir/f'response-{index:02d}.json'
            if not path.is_file():raise ValueError('Cached response batch is missing')
            responses.append(path.read_bytes())
    else:
        base=os.environ.get('LLM_JUDGE_BASE_URL');key=os.environ.get('LLM_JUDGE_API_KEY')
        if not base or not key:raise RuntimeError('Set LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY')
        timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS','300'))
        for index,batch_raw in enumerate(raw_batches,1):
            response=call_judge(base.rstrip('/')+'/v1/responses',key,batch_raw,timeout)
            (args.out/f'response-{index:02d}.json').write_bytes(response)
            responses.append(response)
    envelopes=[json.loads(response) for response in responses]
    parts=[parse_response(envelope,evidence,dict(contract,criteria=batch)) for envelope,batch in zip(envelopes,batches)]
    result=merge_results(parts,contract)
    result.update(response_ids=[envelope.get('id') for envelope in envelopes],model=envelopes[0].get('model'),
                  seconds=round(time.time()-start,2),fresh_call=not bool(args.replay),visual_input=False,rollout_executed=False)
    (args.out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
