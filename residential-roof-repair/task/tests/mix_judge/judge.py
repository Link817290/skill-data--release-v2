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
TASK = Path('/task') if Path('/task/instruction.md').is_file() else HERE.parents[1]
PACKAGE = TASK.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def responses_endpoint(base):
    base = base.strip().rstrip('/')
    if base.endswith('/responses'):
        return base
    if base.endswith('/v1'):
        return base + '/responses'
    return base + '/v1/responses'


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



def table_units(path,prefix):
    from openpyxl import load_workbook
    w=load_workbook(path,data_only=True);units=[]
    for s in w:
        if s.max_row>200:raise ValueError('Workbook needs verified extraction beyond 200 rows per sheet')
        for r,row in enumerate(s.iter_rows(values_only=True),1):
            if any(v is not None for v in row):units.append(dict(id=f'{prefix}-{s.title}-R{r}',text=s.title+' | '+' | '.join('' if v is None else str(v) for v in row)))
    return units

def build_evidence(report,workbook,input_dir,facts_dir):
    reference=PACKAGE/'golden/施工范围说明.docx';reference_book=PACKAGE/'golden/维修询价清单.xlsx'
    candidate=report_units(report,'C');golden=report_units(reference,'G')+table_units(reference_book,'G-W')
    tables=table_units(workbook,'W');sources=[]
    hashes={'candidate_report':sha(report),'candidate_workbook':sha(workbook),'reference_report':sha(reference),'reference_workbook':sha(reference_book)}
    for n,path in enumerate(sorted(input_dir.iterdir()),1):
        if path.suffix=='.docx':sources.extend(report_units(path,f'S{n}'))
        elif path.suffix=='.xlsx':sources.extend(table_units(path,f'S{n}'))
        else:continue
        hashes['source/'+path.name]=sha(path)
    facts=facts_dir/'facts.json';hashes['verified_facts']=sha(facts)
    return dict(candidate=candidate,workbook_sample=tables,golden_meaning=golden,source_materials=sources,verified_facts=[dict(id='F-verified',text=facts.read_text(encoding='utf8'))],scope='Chinese roof-repair enquiry. All source bill rows and all submitted sheets and report paragraphs are extracted; no visual judging. Independent checks own quantity transcription, arithmetic and empty price fields. Judge the business inference and complete scope, not duplicate numeric typos. Sources override Golden.'),hashes


def parse_response(envelope, evidence, contract):
    if envelope.get('status') != 'completed': raise ValueError('Incomplete semantic measurement')
    answer=''.join(c.get('text','') for o in envelope.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text').strip()
    if answer.startswith('```'):answer=answer.split('\n',1)[1].rsplit('```',1)[0]
    result=json.loads(answer)
    if type(result.get('passed')) is not bool:raise ValueError('Verdict must be Boolean')
    if type(result.get('reference_conflict')) is not bool:raise ValueError('Reference conflict must be Boolean')
    rows=result.get('criteria')
    expected={c['id']:c for c in contract['criteria']}
    if not isinstance(rows,list) or len(rows)!=len(expected):raise ValueError('Criteria coverage incomplete')
    if {r.get('id') for r in rows}!=set(expected):raise ValueError('Missing or duplicate criterion')
    units={r['id']:r['text'] for group in ['candidate','workbook_sample','golden_meaning','source_materials','verified_facts'] for r in evidence[group]}
    def normalize(s):return re.sub(r'\s+','',s)
    for row in rows:
        allowed=expected[row['id']].get('allowed_scores',[0,1])
        if type(row.get('score')) not in (int,float) or row['score'] not in allowed:raise ValueError('Invalid criterion score')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():raise ValueError('Reason missing')
        citations=row.get('evidence')
        if isinstance(citations,dict):
            citations=[citations.get('candidate'),citations.get('source')]+list(citations.get('additional') or [])
            citations=[citation for citation in citations if isinstance(citation,dict)]
            row['evidence']=citations
        if not isinstance(citations,list) or not citations:raise ValueError('Evidence missing')
        bound=[]
        for citation in citations:
            key=citation.get('id');quote=citation.get('quote')
            if key in units and isinstance(quote,str) and normalize(quote) and normalize(quote) in normalize(units[key]):bound.append(citation)
        if not bound:raise ValueError('No semantic evidence citation can be bound')
        if row['score']>0 and not any(c['id'].startswith(('C','W')) for c in bound):raise ValueError('Positive credit requires candidate evidence')
        if not any(c['id'].startswith(('G','S','F')) for c in bound):raise ValueError('Criterion requires reference or source evidence')
        row['evidence']=bound
    passed=all(r['score']==1 for r in rows) and not result['reference_conflict']
    if result['passed']!=passed:raise ValueError('Overall verdict inconsistent with criteria')
    result['semantic_score']=None if result['reference_conflict'] else round(sum(expected[r['id']]['weight']*r['score'] for r in rows),6)
    result['measurement_status']='reference_conflict_requires_review' if result['reference_conflict'] else 'completed'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--input',type=Path,default=TASK/'environment/workspace/input')
    parser.add_argument('--facts',type=Path,default=TASK/'tests/reference')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--replay',type=Path)
    args=parser.parse_args()
    contract=json.loads((HERE/'contract.json').read_text(encoding='utf-8'))
    settings=json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
    evidence,hashes=build_evidence(args.report,args.workbook,args.input,args.facts)
    prompt=(HERE/'prompt.md').read_text(encoding='utf-8')
    text=prompt+'\nCriteria:\n'+json.dumps(contract['criteria'],ensure_ascii=False)+'\nEvidence:\n'+json.dumps(evidence,ensure_ascii=False)
    schema=json.loads((HERE/'response.schema.json').read_text(encoding='utf-8'))
    body=dict(model=os.environ.get('LLM_JUDGE_MODEL',settings['model']),store=False,max_output_tokens=settings['max_output_tokens'],input=[dict(role='user',content=[dict(type='input_text',text=text)])],
        text={'format':{'type':'json_schema','name':'roof_source_bound_review','strict':True,'schema':schema}})
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'response.json').exists() and not args.replay:raise ValueError('Output already contains a response; choose a new output folder')
    raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
    (args.out/'request.json').write_bytes(raw)
    (args.out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.out/'manifest.json').write_text(json.dumps(dict(artifact_hashes=hashes,request_sha256=hashlib.sha256(raw).hexdigest(),
        rollout_executed=False,visual_input=False,contract_sha256=sha(HERE/'contract.json')),ensure_ascii=False,indent=2),encoding='utf-8')
    start=time.time()
    if args.replay:
        prior_manifest=json.loads((args.replay.parent/'manifest.json').read_text(encoding='utf-8'))
        if prior_manifest.get('request_sha256')!=hashlib.sha256(raw).hexdigest():
            raise ValueError('Cached response belongs to a different request; run a fresh review')
        if args.out.resolve()==args.replay.parent.resolve():
            raise ValueError('Replay must not overwrite its archived source evidence')
        response=args.replay.read_bytes()
    else:
        base=os.environ.get('LLM_JUDGE_BASE_URL');key=os.environ.get('LLM_JUDGE_API_KEY')
        if not base or not key:raise RuntimeError('Set LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY')
        req=urllib.request.Request(responses_endpoint(base),data=raw,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        timeout=int(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS','300'))
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as stream:response=stream.read()
    (args.out/'response.json').write_bytes(response)
    envelope=json.loads(response);result=parse_response(envelope,evidence,contract)
    result.update(response_id=envelope.get('id'),model=envelope.get('model'),seconds=round(time.time()-start,2),fresh_call=not bool(args.replay),visual_input=False,rollout_executed=False)
    (args.out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
