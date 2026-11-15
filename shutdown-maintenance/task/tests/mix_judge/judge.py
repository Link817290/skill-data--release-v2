"""Text-only, source-bound semantic comparison. Never launches a solving agent."""
import argparse
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

import fitz
from docx import Document
import csv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):
    return re.sub(r'\s+', '', text)


def citation_bound(quote, unit):
    q = normalize(quote)
    u = normalize(unit)
    if q and q in u:
        return True
    # A judge may quote the sentence around a clarifying parenthetical. Only a
    # complete balanced parenthetical may be elided; all remaining text must
    # still be an exact contiguous substring of the cited evidence unit.
    without_parenthetical = re.sub(r'[（(][^（）()]*[）)]', '', u)
    return bool(q) and q in without_parenthetical


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
            p=(folder/name if group=='candidate' else ROOT/'tests/reference/business-golden-v4.xlsx')
            evidence[group]+=extract(p,f'{prefix}{i}')
            hashes[group+'/'+name]=sha(p)
    for i,p in enumerate(sorted(input_dir.rglob('*')),1):
        if p.is_file():
            units=extract(p,f'S{i}')
            if units:evidence['source_materials']+=units;hashes['source/'+p.relative_to(input_dir).as_posix()]=sha(p)
    fp=ROOT/'tests/reference/facts.json'
    evidence['verified_facts']=[dict(id='F1',text=fp.read_text(encoding='utf8'))];hashes['facts']=sha(fp)
    evidence['scope']='All supplied business document text and table rows. No visual assessment. Source evidence takes precedence over reference.'
    return evidence,hashes


def response_schema(evidence, contract):
    candidate_ids = [row['id'] for row in evidence['candidate']]
    reference_ids = [row['id'] for group in ['golden_meaning', 'source_materials', 'verified_facts']
                     for row in evidence[group]]
    def selected_ids(values):
        return {'type': 'array', 'items': {'type': 'string', 'enum': values},
                'minItems': 1, 'maxItems': 3}
    properties = {}
    for criterion in contract['criteria']:
        properties[criterion['id']] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'score': {'type': 'number', 'enum': criterion.get('completion_scale', [0, 0.5, 1])},
                'reason': {'type': 'string'},
                'candidate_ids': selected_ids(candidate_ids),
                'reference_ids': selected_ids(reference_ids),
            },
            'required': ['score', 'reason', 'candidate_ids', 'reference_ids'],
        }
    return {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'reference_conflict': {'type': 'boolean'},
            'criteria': {'type': 'object', 'additionalProperties': False,
                         'properties': properties, 'required': list(properties)},
            'notes': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['reference_conflict', 'criteria', 'notes'],
    }

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
    candidate_ids={row['id'] for row in evidence['candidate']}
    reference_ids=set(units)-candidate_ids
    rows=[]
    for identifier in expected:
        decision=decisions[identifier]
        if (type(decision.get('score')) not in (int,float)
                or decision['score'] not in expected[identifier].get('completion_scale', [0,0.5,1])):
            raise ValueError('Invalid criterion score')
        if not isinstance(decision.get('reason'),str) or not decision['reason'].strip():raise ValueError('Reason missing')
        for key,allowed in [('candidate_ids',candidate_ids),('reference_ids',reference_ids)]:
            selected=decision.get(key)
            if (not isinstance(selected,list) or not 1<=len(selected)<=3
                    or any(type(value) is not str or value not in allowed for value in selected)
                    or len(set(selected))!=len(selected)):
                raise ValueError('Invalid evidence-unit selection: '+identifier+'/'+key)
        citations=[{'id':key,'quote':units[key],'quote_origin':'runtime_exact_evidence_unit'}
                   for key in decision['candidate_ids']+decision['reference_ids']]
        rows.append({'id':identifier,'score':decision['score'],'reason':decision['reason'],'evidence':citations})
    passed=all(r['score']==1 for r in rows) and not result['reference_conflict']
    result['criteria']=rows
    result['passed']=passed
    result['evidence_binding']='model_selected_ids_runtime_exact_full_unit_text_v1'
    result['semantic_score']=None if result['reference_conflict'] else round(sum(expected[r['id']]['weight']*r['score'] for r in rows),6)
    result['measurement_status']='reference_conflict_requires_review' if result['reference_conflict'] else 'completed'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--submission-dir',type=Path,required=True)
    parser.add_argument('--input',type=Path,default=ROOT/'environment/workspace/input')
    parser.add_argument('--facts',type=Path,default=ROOT/'tests/reference')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--replay',type=Path)
    args=parser.parse_args()
    contract=json.loads((HERE/'contract.json').read_text(encoding='utf-8'))
    settings=json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
    evidence,hashes=build_evidence(args.submission_dir,args.input)
    prompt=(HERE/'prompt.md').read_text(encoding='utf-8')
    text=prompt+'\nCriteria:\n'+json.dumps(contract['criteria'],ensure_ascii=False)+'\nEvidence:\n'+json.dumps(evidence,ensure_ascii=False)
    body=dict(model=settings['model'],store=False,max_output_tokens=settings['max_output_tokens'],input=[dict(role='user',content=[dict(type='input_text',text=text)])])
    body['text']={'format':{'type':'json_schema','name':'shutdown_maintenance_semantic_review','strict':True,
                            'schema':response_schema(evidence,contract)}}
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'response.json').exists() and not args.replay:raise ValueError('Output already contains a response; choose a new output folder')
    raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
    (args.out/'request.json').write_bytes(raw)
    (args.out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.out/'manifest.json').write_text(json.dumps(dict(artifact_hashes=hashes,request_sha256=hashlib.sha256(raw).hexdigest(),
        rollout_executed=False,visual_input=False,contract_sha256=sha(HERE/'contract.json')),ensure_ascii=False,indent=2),encoding='utf-8')
    start=time.time()
    mode=os.environ.get('LLM_JUDGE_MODE','fresh').strip().lower()
    replay_path=args.replay
    if mode=='replay' and not replay_path:
        cache_root=Path(os.environ.get('LLM_JUDGE_CACHE_DIR',str(HERE/'cache')))
        replay_path=cache_root/hashlib.sha256(raw).hexdigest()/'response.json'
        if not replay_path.is_file():raise RuntimeError('Exact request-bound semantic replay unavailable')
        cached_request=replay_path.parent/'request.json'
        if not cached_request.is_file() or cached_request.read_bytes()!=raw:
            raise RuntimeError('Replay cache request bytes do not match')
    if replay_path:
        prior_manifest=json.loads((replay_path.parent/'manifest.json').read_text(encoding='utf-8'))
        if prior_manifest.get('request_sha256')!=hashlib.sha256(raw).hexdigest():
            raise ValueError('Cached response belongs to a different request; run a fresh review')
        if args.out.resolve()==replay_path.parent.resolve():
            raise ValueError('Replay must not overwrite its archived source evidence')
        response=replay_path.read_bytes()
    else:
        base=os.environ.get('LLM_JUDGE_BASE_URL');key=os.environ.get('LLM_JUDGE_API_KEY')
        if not base or not key:raise RuntimeError('Set LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY')
        req=urllib.request.Request(base.rstrip('/')+'/v1/responses',data=raw,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=180) as stream:response=stream.read()
    (args.out/'response.json').write_bytes(response)
    envelope=json.loads(response);result=parse_response(envelope,evidence,contract)
    result.update(response_id=envelope.get('id'),model=envelope.get('model'),seconds=round(time.time()-start,2),fresh_call=not bool(replay_path),visual_input=False,rollout_executed=False)
    (args.out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
