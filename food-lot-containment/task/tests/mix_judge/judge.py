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



def build_evidence(report, registers, input_dir, facts_dir):
    choices=[p for p in (ROOT/'golden').iterdir() if p.name in ('trade-recall-notice.pdf','trade-recall-notice.docx')]
    if len(choices)!=1:raise ValueError('Exactly one Golden notice is required')
    reference=choices[0];candidate=report_units(report,'C');golden=report_units(reference,'G')
    sources=[];tables=[];hashes={'candidate_notice':sha(report),'reference_notice':sha(reference)}
    for n,name in enumerate(['product-scope.csv','pack-changes.csv','distribution-list.csv'],1):
        path=registers/name
        with path.open(encoding='utf-8-sig',newline='') as f:
            for r,row in enumerate(csv.reader(f),1):tables.append(dict(id=f'W{n}-R{r}',text=' | '.join(row)))
        hashes['candidate/'+name]=sha(path)
    prep=registers/'preparation'
    for n,path in enumerate(sorted(prep.rglob('*')),1):
        if path.is_file() and path.suffix.lower() in ('.md','.txt','.py','.sh'):
            content=path.read_text(encoding='utf-8-sig')
            if len(content)>120000:raise ValueError('Preparation evidence requires a bounded manual extraction')
            candidate.append(dict(id=f'C-PREP-{n}',text=path.relative_to(prep).as_posix()+'\n'+content))
            hashes['candidate/preparation/'+path.relative_to(prep).as_posix()]=sha(path)
    for n,path in enumerate(sorted(input_dir.rglob('*')),1):
        if not path.is_file() or path.name.startswith('~$'):continue
        if path.suffix.lower() in ('.pdf','.docx'):sources.extend(report_units(path,f'S{n}-'))
        elif path.suffix.lower() in ('.csv','.txt'):
            sources.extend(dict(id=f'S{n}-R{i}',text=line) for i,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1) if line.strip())
        else:continue
        hashes['source/'+path.relative_to(input_dir).as_posix()]=sha(path)
    path=facts_dir/'facts.json';facts=[dict(id='F-verified',text=path.read_text(encoding='utf-8-sig'))];hashes['verified_facts/facts.json']=sha(path)
    return dict(candidate=candidate,workbook_sample=tables,golden_meaning=golden,source_materials=sources,verified_facts=facts,
        scope='Text-only trade communication review. Every CSV row and supplied notice is included. Registers are also independently checked in full. No visual or style matching.'),hashes

def response_schema(evidence, contract):
    criterion_ids=[row['id'] for row in contract['criteria']]
    candidate_ids=[row['id'] for group in ['candidate','workbook_sample'] for row in evidence[group]]
    narrative_ids=[row['id'] for row in evidence['candidate']]
    reference_ids=[row['id'] for group in ['golden_meaning','source_materials','verified_facts'] for row in evidence[group]]
    def selected(values):
        return dict(type='array',items=dict(type='string',enum=values),minItems=1,maxItems=2)
    criteria={}
    for identifier in criterion_ids:
        criteria[identifier]=dict(type='object',additionalProperties=False,
            properties=dict(score=dict(type='number',enum=[0,.5,1]),reason=dict(type='string'),
                candidate_ids=selected(candidate_ids),reference_ids=selected(reference_ids)),
            required=['score','reason','candidate_ids','reference_ids'])
    audit={}
    for identifier in narrative_ids:
        audit[identifier]=dict(type='object',additionalProperties=False,
            properties=dict(verdict=dict(type='string',enum=['supports','neutral','contradicts']),
                affected_criteria=dict(type='array',items=dict(type='string',enum=criterion_ids),uniqueItems=True)),
            required=['verdict','affected_criteria'])
    return dict(type='object',additionalProperties=False,
        properties=dict(reference_conflict=dict(type='boolean'),
            criteria=dict(type='object',additionalProperties=False,properties=criteria,required=criterion_ids),
            candidate_unit_audit=dict(type='object',additionalProperties=False,properties=audit,required=narrative_ids),
            notes=dict(type='array',items=dict(type='string'))),
        required=['reference_conflict','criteria','candidate_unit_audit','notes'])


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
    narrative_ids={r['id'] for r in evidence['candidate']}
    reference_ids=set(units)-candidate_ids
    audit=result.get('candidate_unit_audit')
    if not isinstance(audit,dict) or set(audit)!=narrative_ids:raise ValueError('Candidate narrative audit incomplete')
    contradictions={identifier:set() for identifier in expected}
    for unit_id,row in audit.items():
        verdict=row.get('verdict');affected=row.get('affected_criteria')
        if verdict not in ['supports','neutral','contradicts'] or not isinstance(affected,list) or any(x not in expected for x in affected):
            raise ValueError('Invalid candidate-unit audit: '+unit_id)
        if verdict=='contradicts' and not affected:raise ValueError('Contradiction must identify affected criteria')
        if verdict=='neutral' and affected:raise ValueError('Neutral unit cannot identify affected criteria')
        if verdict=='contradicts':
            for identifier in affected:contradictions[identifier].add(unit_id)
    rows=[]
    for identifier in expected:
        row=decisions[identifier]
        if type(row.get('score')) not in (int,float) or row['score'] not in [0,0.5,1]:raise ValueError('Invalid criterion score')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():raise ValueError('Reason missing')
        for field,allowed in [('candidate_ids',candidate_ids),('reference_ids',reference_ids)]:
            selected=row.get(field)
            if not isinstance(selected,list) or not 1<=len(selected)<=2 or any(x not in allowed for x in selected) or len(set(selected))!=len(selected):
                raise ValueError('Invalid evidence-unit selection: '+identifier+'/'+field)
        if contradictions[identifier] and row['score']!=0:raise ValueError('Contradicted criterion must score zero: '+identifier)
        citations=[dict(id=key,quote=units[key],quote_origin='runtime_exact_evidence_unit')
                   for key in row['candidate_ids']+row['reference_ids']]
        rows.append(dict(id=identifier,score=row['score'],reason=row['reason'],evidence=citations,
                         contradiction_units=sorted(contradictions[identifier])))
    passed=all(r['score']==1 for r in rows) and not result['reference_conflict']
    result['criteria']=rows;result['passed']=passed
    result['evidence_binding']='model_selected_ids_runtime_exact_full_unit_text_v1'
    result['semantic_score']=None if result['reference_conflict'] else round(sum(expected[r['id']]['weight']*r['score'] for r in rows),6)
    result['measurement_status']='reference_conflict_requires_review' if result['reference_conflict'] else 'completed'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--registers',type=Path,required=True)
    parser.add_argument('--input',type=Path,default=TASK_ROOT/'environment/workspace/input')
    parser.add_argument('--facts',type=Path,default=TASK_ROOT/'tests/reference')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--replay',type=Path)
    args=parser.parse_args()
    contract=json.loads((HERE/'contract.json').read_text(encoding='utf-8'))
    settings=json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
    evidence,hashes=build_evidence(args.report,args.registers,args.input,args.facts)
    prompt=(HERE/'prompt.md').read_text(encoding='utf-8')
    text=prompt+'\nCriteria:\n'+json.dumps(contract['criteria'],ensure_ascii=False)+'\nEvidence:\n'+json.dumps(evidence,ensure_ascii=False)
    body=dict(model=os.environ.get('LLM_JUDGE_MODEL',settings['model']),store=False,max_output_tokens=settings['max_output_tokens'],input=[dict(role='user',content=[dict(type='input_text',text=text)])])
    body['text']={'format':{'type':'json_schema','name':'source_bound_food_review','strict':True,
                            'schema':response_schema(evidence,contract)}}
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'response.json').exists() and not args.replay:raise ValueError('Output already contains a response; choose a new output folder')
    raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
    request_sha256=hashlib.sha256(raw).hexdigest()
    cache_identity={'request_sha256':request_sha256,'artifact_hashes':hashes,
                    'contract_sha256':sha(HERE/'contract.json')}
    cache_key=hashlib.sha256(json.dumps(cache_identity,ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode()).hexdigest()
    (args.out/'request.json').write_bytes(raw)
    (args.out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.out/'manifest.json').write_text(json.dumps(dict(artifact_hashes=hashes,request_sha256=hashlib.sha256(raw).hexdigest(),
        rollout_executed=False,visual_input=False,contract_sha256=sha(HERE/'contract.json')),ensure_ascii=False,indent=2),encoding='utf-8')
    start=time.time()
    mode=os.environ.get('LLM_JUDGE_MODE','fresh')
    if mode not in ('fresh','replay'):raise ValueError('LLM_JUDGE_MODE must be fresh or replay')
    fresh_call=False
    if args.replay:
        prior_manifest=json.loads((args.replay.parent/'manifest.json').read_text(encoding='utf-8'))
        if prior_manifest.get('request_sha256')!=hashlib.sha256(raw).hexdigest():
            raise ValueError('Cached response belongs to a different request; run a fresh review')
        if prior_manifest.get('artifact_hashes')!=hashes:
            raise ValueError('Cached response belongs to different artifact bytes; run a fresh review')
        if args.out.resolve()==args.replay.parent.resolve():
            raise ValueError('Replay must not overwrite its archived source evidence')
        response=args.replay.read_bytes()
    elif mode=='replay':
        cache_root=Path(os.environ.get('LLM_JUDGE_CACHE_DIR',HERE/'cache'))
        cached=cache_root/cache_key/'response.json'
        if not cached.is_file():raise ValueError('No request-bound semantic replay is available')
        response=cached.read_bytes()
    else:
        base=os.environ.get('LLM_JUDGE_BASE_URL');key=os.environ.get('LLM_JUDGE_API_KEY')
        if not base or not key:raise RuntimeError('Set LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY')
        endpoint = base if base.endswith('/responses') else base + ('/responses' if base.endswith('/v1') else '/v1/responses')
        req=urllib.request.Request(endpoint,data=raw,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS','180'))
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as stream:response=stream.read()
        fresh_call=True
    (args.out/'response.json').write_bytes(response)
    envelope=json.loads(response);result=parse_response(envelope,evidence,contract)
    result.update(response_id=envelope.get('id'),model=envelope.get('model'),seconds=round(time.time()-start,2),fresh_call=fresh_call,visual_input=False,rollout_executed=False)
    (args.out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
