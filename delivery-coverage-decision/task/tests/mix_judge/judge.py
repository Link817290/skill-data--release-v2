"""Text-only, source-bound semantic comparison. Never launches a solving agent."""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import fitz
from docx import Document
from openpyxl import load_workbook

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


def build_evidence(report, workbook, input_dir, facts_dir):
    if facts_dir.resolve() != (TASK_ROOT/'tests/reference').resolve():
        raise ValueError('Unverified legacy facts override is unsupported by this source-certified runtime')
    reference = next((ROOT / 'golden').glob('*.pdf'))
    candidate = report_units(report, 'C')
    reference_units = report_units(reference, 'G')
    sources = []
    hashes = {'candidate_report':sha(report), 'reference_report':sha(reference), 'candidate_workbook':sha(workbook)}
    for n, path in enumerate(sorted((input_dir / '业务文件').glob('*.docx')), 1):
        if path.name.startswith('~$'): continue
        sources.extend(report_units(path, f'S{n}'))
        hashes['source/' + path.name] = sha(path)
    workbook_evidence = []
    book = load_workbook(workbook, read_only=True, data_only=False)
    # Text evidence is sampled; numerical validation is explicitly separate.
    for s, sheet in enumerate(book, 1):
        workbook_evidence.append(dict(id=f'W{s}-TITLE', text=sheet.title))
        limit = min(sheet.max_row, 30)
        for n, row in enumerate(sheet.iter_rows(max_row=limit, values_only=True), 1):
            text = ' | '.join('' if x is None else str(x) for x in row)
            if text.replace('|','').strip():workbook_evidence.append(dict(id=f'W{s}-R{n}',text=text))
    book.close()
    # Certify the current reference carrier against raw inputs before using its
    # numerical tables. This certificate does not certify report narrative.
    sys.path.insert(0,str(HERE.parent))
    from workbook_verify import verify_workbook,WorkbookData
    reference_workbook=ROOT/'golden/analysis.xlsx'
    verified=verify_workbook(input_dir,reference_workbook)
    if not verified['passed']:
        raise ValueError('Reference numerical tables failed independent source verification')
    carrier=WorkbookData(reference_workbook,input_dir/'配送方案交付模板.xlsx')
    facts=[]
    try:
        for identifier,sheet in [('decision','决策摘要'),('data_quality','数据核对'),
                                 ('plan_comparison','方案比较'),('scenario_summary','工况结果')]:
            rows=list(carrier.rows(sheet).values())
            text=json.dumps(rows,ensure_ascii=False,sort_keys=True)
            facts.append(dict(id='F-'+identifier,text=text))
            hashes['verified_facts/'+identifier]=hashlib.sha256(text.encode()).hexdigest()
    finally:carrier.close()
    facts.append(dict(id='F-source-verification',text=json.dumps({
        'reference_workbook_sha256':sha(reference_workbook),
        'numeric_runtime_sha256':{name:sha(HERE.parent/name) for name in ['workbook_verify.py','independent.py','verify.py']},
        'source_input_sha256':{str(path.relative_to(input_dir)):sha(path) for path in sorted(input_dir.rglob('*')) if path.is_file()},
        'all_numerical_criteria_passed':True,
        'scope':'Current reference workbook tables were independently checked against original inputs. This does not certify every narrative claim in the reference report.'},sort_keys=True)))
    return dict(candidate=candidate, workbook_sample=workbook_evidence, golden_meaning=reference_units,
                source_materials=sources, verified_facts=facts,
                scope='Text and table semantics only. Candidate workbook rows are sampled; current reference numerical tables have independent source verification. No visual score is implied.'), hashes


def response_schema(evidence, contract):
    candidate_ids = [r['id'] for group in ['candidate', 'workbook_sample'] for r in evidence[group]]
    reference_ids = [r['id'] for group in ['golden_meaning', 'source_materials', 'verified_facts'] for r in evidence[group]]
    def ids(values):
        return dict(type='array', items=dict(type='string', enum=values), minItems=1, maxItems=2)
    properties = {}
    for criterion in contract['criteria']:
        properties[criterion['id']] = dict(type='object', additionalProperties=False,
            properties=dict(score=dict(type='number', enum=[0, 0.5, 1]),
                reason=dict(type='string'), candidate_ids=ids(candidate_ids), reference_ids=ids(reference_ids)),
            required=['score', 'reason', 'candidate_ids', 'reference_ids'])
    return dict(type='object', additionalProperties=False,
        properties=dict(reference_conflict=dict(type='boolean'),
            criteria=dict(type='object', additionalProperties=False, properties=properties, required=list(properties)),
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
        if type(row.get('score')) not in (int,float) or row['score'] not in [0,0.5,1]:raise ValueError('Invalid criterion score')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():raise ValueError('Reason missing')
        for key,allowed in [('candidate_ids',candidate_ids),('reference_ids',reference_ids)]:
            selected=row.get(key)
            if not isinstance(selected,list) or not 1<=len(selected)<=2 or any(type(x) is not str or x not in allowed for x in selected):
                raise ValueError('Invalid evidence-unit selection: '+identifier+'/'+key)
            if len(set(selected))!=len(selected):raise ValueError('Duplicate evidence-unit selection')
        # The model chooses existing units; the runtime attaches their exact text.
        # These are full-unit bindings, not quotations generated by the model.
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


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--input',type=Path,default=TASK_ROOT/'environment/workspace/input')
    parser.add_argument('--facts',type=Path,default=TASK_ROOT/'tests/reference')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--replay',type=Path)
    args=parser.parse_args()
    contract=json.loads((HERE/'contract.json').read_text(encoding='utf-8'))
    settings=json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
    evidence,hashes=build_evidence(args.report,args.workbook,args.input,args.facts)
    prompt=(HERE/'prompt.md').read_text(encoding='utf-8')
    text=prompt+'\nCriteria:\n'+json.dumps(contract['criteria'],ensure_ascii=False)+'\nEvidence:\n'+json.dumps(evidence,ensure_ascii=False)
    body=dict(model=os.environ.get('LLM_JUDGE_MODEL',settings['model']),store=False,max_output_tokens=settings['max_output_tokens'],input=[dict(role='user',content=[dict(type='input_text',text=text)])])
    body['text']={'format':{'type':'json_schema','name':'source_bound_semantic_review','strict':True,
                            'schema':response_schema(evidence,contract)}}
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'response.json').exists() and not args.replay:raise ValueError('Output already contains a response; choose a new output folder')
    raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
    (args.out/'request.json').write_bytes(raw)
    (args.out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.out/'manifest.json').write_text(json.dumps(dict(artifact_hashes=hashes,request_sha256=hashlib.sha256(raw).hexdigest(),
        rollout_executed=False,visual_input=False,contract_sha256=sha(HERE/'contract.json')),ensure_ascii=False,indent=2),encoding='utf-8')
    request_sha256=hashlib.sha256(raw).hexdigest()
    cache_identity={'request_sha256':request_sha256,'artifact_hashes':hashes,
                    'contract_sha256':sha(HERE/'contract.json')}
    cache_key=hashlib.sha256(json.dumps(cache_identity,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    start=time.time();fresh_call=False
    if args.replay:
        prior_manifest=json.loads((args.replay.parent/'manifest.json').read_text(encoding='utf-8'))
        if prior_manifest.get('request_sha256')!=hashlib.sha256(raw).hexdigest():
            raise ValueError('Cached response belongs to a different request; run a fresh review')
        if prior_manifest.get('artifact_hashes')!=hashes:
            raise ValueError('Cached response belongs to different artifact bytes; run a fresh review')
        if args.out.resolve()==args.replay.parent.resolve():
            raise ValueError('Replay must not overwrite its archived source evidence')
        response=args.replay.read_bytes()
    elif os.environ.get('LLM_JUDGE_MODE','fresh')=='replay':
        cache_root=Path(os.environ.get('LLM_JUDGE_CACHE_DIR',HERE/'cache'))
        cached=cache_root/cache_key/'response.json'
        if not cached.is_file():raise ValueError('No request-bound semantic replay is available')
        response=cached.read_bytes()
    else:
        if os.environ.get('LLM_JUDGE_MODE','fresh')!='fresh':raise ValueError('LLM_JUDGE_MODE must be fresh or replay')
        base=os.environ.get('LLM_JUDGE_BASE_URL');key=os.environ.get('LLM_JUDGE_API_KEY')
        if not base or not key:raise RuntimeError('Set LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY')
        req=urllib.request.Request(base.rstrip('/')+'/v1/responses',data=raw,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS','180'))
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as stream:response=stream.read()
        fresh_call=True
    (args.out/'response.json').write_bytes(response)
    envelope=json.loads(response);result=parse_response(envelope,evidence,contract)
    result.update(response_id=envelope.get('id'),model=envelope.get('model'),seconds=round(time.time()-start,2),fresh_call=fresh_call,visual_input=False,rollout_executed=False)
    (args.out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
