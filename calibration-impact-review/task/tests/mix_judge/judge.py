"""Text-only, source-bound semantic comparison. Never launches a solving agent."""
import argparse
import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

from docx import Document

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_units(path, prefix):
    units = []
    if path.suffix.lower() == '.pdf':
        import fitz
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
    elif path.suffix.lower() == '.md':
        units.extend(dict(id=f'{prefix}-P{i}',text=block.strip()) for i,block in enumerate(re.split(r'\n\s*\n',path.read_text(encoding='utf-8-sig'))) if block.strip())
    else:
        raise ValueError('Unsupported evidence format')
    if not units:
        raise ValueError('No report text extracted; OCR or another verified extraction is required')
    return units



def build_evidence(report, workbook, input_dir, facts_dir):
    reference=Path('/reference/README.md') if Path('/reference/README.md').is_file() else HERE.parent.parent.parent/'golden/measurement-check/README.md'
    candidate=report_units(report,'C');golden=report_units(reference,'G')
    hashes={'candidate_readme':sha(report),'candidate_results':sha(workbook),'reference_readme':sha(reference)}
    sources=[]
    for n,path in enumerate(sorted(input_dir.rglob('*')),1):
        if not path.is_file() or path.name.startswith('~$'):continue
        prefix=f'S{n}-';suffix=path.suffix.lower()
        if suffix in ('.docx','.pdf'):sources.extend(report_units(path,prefix))
        elif suffix in ('.csv','.json','.txt','.md'):
            lines=path.read_text(encoding='utf-8-sig').splitlines()
            sources.extend(dict(id=f'{prefix}R{i}',text=line) for i,line in enumerate(lines,1) if line.strip())
        else:continue
        hashes['source/'+path.relative_to(input_dir).as_posix()]=sha(path)
    result=json.loads(workbook.read_text(encoding='utf-8-sig'));observed=[]
    for key in ['summary','baseline','optical_limits','daily_results','trend','scope']:
        if key in result:observed.append(dict(id='W-'+key,text=json.dumps(result[key],ensure_ascii=False)))
    for key in ['mass_results','optical_results']:
        for row in result.get(key,[]):
            if row.get('bias_failure') or row.get('precision_failure') or row.get('failure'):
                observed.append(dict(id='W-'+key+'-'+str(row.get('record_id')),text=json.dumps(row,ensure_ascii=False)))
    exceptions=workbook.parent/'exceptions.csv'
    if exceptions.is_file():
        hashes['candidate_exceptions']=sha(exceptions)
        observed.extend(dict(id=f'W-CSV-{i}',text=line) for i,line in enumerate(exceptions.read_text(encoding='utf-8-sig').splitlines()) if line.strip())
    path=facts_dir/'facts.json';facts=[dict(id='F-verified',text=path.read_text(encoding='utf-8-sig'))];hashes['verified_facts/facts.json']=sha(path)
    rules=Path('/reference/skills') if Path('/reference/skills').is_dir() else ROOT/'environment/skills'
    for index,path in enumerate(sorted(rules.rglob('*.md'))):
        facts.append(dict(id=f'F-rule-{index}',text=path.read_text(encoding='utf-8-sig')))
        hashes['professional_rule/'+path.relative_to(rules).as_posix()]=sha(path)
    return dict(candidate=candidate,workbook_sample=observed,golden_meaning=golden,source_materials=sources,verified_facts=facts,
        scope='Content-only review of README, supplied-run JSON and exceptions. Complete source CSV rows are included. Independent execution verifies all records and altered-input cases. JSON excerpts include summaries, limits, daily scope, trends and failures; infer no unshown candidate values.'),hashes


def response_format():
    schema=json.loads((HERE/'response.schema.json').read_text(encoding='utf-8'))
    return {'type':'json_schema','name':'calibration_impact_review','strict':True,'schema':schema}


def parse_response(envelope, evidence, contract):
    if envelope.get('status') != 'completed': raise ValueError('Incomplete semantic measurement')
    messages=[c.get('text','').strip() for o in envelope.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text' and c.get('text','').strip()]
    if not messages:raise ValueError('Structured semantic response missing')
    answer=messages[-1]
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
        if type(row.get('score')) not in (int,float) or row['score'] not in [0,0.5,1]:raise ValueError('Invalid criterion score')
        if type(row.get('meets_brief')) is not bool:raise ValueError('Missing independent core-completion verdict')
        if row['meets_brief'] is False and row['score'] != 0:
            raise ValueError('A failed core-completion verdict requires criterion score 0')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():raise ValueError('Reason missing')
        citations=row.get('evidence')
        if not isinstance(citations,list) or not 2<=len(citations)<=4:raise ValueError('Two-sided evidence missing')
        for citation in citations:
            key=citation.get('id');quote=citation.get('quote')
            if key not in units or not isinstance(quote,str) or not normalize(quote) or normalize(quote) not in normalize(units[key]):
                raise ValueError('Unbound semantic evidence: '+str(key))
        if not any(c['id'].startswith(('C','W')) for c in citations):raise ValueError('Every verdict requires candidate evidence')
        if not any(c['id'].startswith(('G','S','F')) for c in citations):raise ValueError('Criterion requires reference or source evidence')
    passed=all(r['score']==1 for r in rows) and not result['reference_conflict']
    if result['passed']!=passed:raise ValueError('Overall verdict inconsistent with criteria')
    result['semantic_score']=None if result['reference_conflict'] else round(sum(expected[r['id']]['weight']*r['score'] for r in rows),6)
    result['completion']={row['id']:row['meets_brief'] for row in rows}
    result['measurement_status']='reference_conflict_requires_review' if result['reference_conflict'] else 'completed'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--readme',dest='report',type=Path,required=True)
    parser.add_argument('--results',dest='workbook',type=Path,required=True)
    parser.add_argument('--input',type=Path,default=ROOT/'environment/workspace/input')
    parser.add_argument('--facts',type=Path,default=ROOT/'tests/reference')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--replay',type=Path)
    args=parser.parse_args()
    contract=json.loads((HERE/'contract.json').read_text(encoding='utf-8'))
    settings=json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
    evidence,hashes=build_evidence(args.report,args.workbook,args.input,args.facts)
    prompt=(HERE/'prompt.md').read_text(encoding='utf-8')
    text=prompt+'\nCriteria:\n'+json.dumps(contract['criteria'],ensure_ascii=False)+'\nIndependent completion requirements:\n'+json.dumps(contract['completion_requirements'],ensure_ascii=False)+'\nEvidence:\n'+json.dumps(evidence,ensure_ascii=False)
    model=os.environ.get('LLM_JUDGE_MODEL',settings['model'])
    body=dict(model=model,store=False,reasoning={'effort':'high'},max_output_tokens=settings['max_output_tokens'],input=[dict(role='user',content=[dict(type='input_text',text=text)])])
    body['text']={'format':response_format()}
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'response.json').exists():raise ValueError('Output already contains a response; choose a new output folder')
    raw=json.dumps(body,ensure_ascii=False,sort_keys=True).encode('utf-8')
    base_identity=hashlib.sha256(raw).hexdigest();identity=base_identity
    contract_hash=sha(HERE/'contract.json')
    cache_identity={'base_request_sha256':base_identity,'artifact_hashes':hashes,'contract_sha256':contract_hash}
    cache_key=hashlib.sha256(json.dumps(cache_identity,ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode('utf-8')).hexdigest()
    cache_value=os.environ.get('LLM_JUDGE_CACHE_DIR') or os.environ.get('LLM_JUDGE_CACHE')
    cache_root=Path(cache_value) if cache_value else None
    timeout=float(os.environ.get('LLM_JUDGE_TIMEOUT_SECONDS') or os.environ.get('LLM_JUDGE_TIMEOUT_SEC') or '600')
    if not 0 < timeout <= 3600:raise ValueError('LLM_JUDGE_TIMEOUT_SECONDS must be in (0, 3600]')
    cache_entry=cache_root/cache_key if cache_root else None
    (args.out/'request.json').write_bytes(raw)
    (args.out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=dict(artifact_hashes=hashes,base_request_sha256=base_identity,request_sha256=identity,
        cache_key=cache_key,visual_input=False,contract_sha256=contract_hash)
    (args.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    start=time.time()
    origin='live'
    if args.replay:
        archive=args.replay.parent
        prior_manifest=json.loads((archive/'manifest.json').read_text(encoding='utf-8'))
        if (prior_manifest.get('base_request_sha256')!=base_identity
                or any(prior_manifest.get(key)!=manifest[key] for key in ('artifact_hashes','contract_sha256','cache_key'))):
            raise ValueError('Cached response belongs to a different request; run a fresh review')
        if args.out.resolve()==args.replay.parent.resolve():
            raise ValueError('Replay must not overwrite its archived source evidence')
        response=args.replay.read_bytes()
        identity=prior_manifest['request_sha256']
        manifest=prior_manifest
        shutil.copyfile(archive/'request.json',args.out/'request.json')
        shutil.copyfile(archive/'manifest.json',args.out/'manifest.json')
        origin='explicit_replay'
    elif cache_entry and all((cache_entry/name).is_file() for name in ('request.json','response.json','manifest.json')):
        cached_manifest=json.loads((cache_entry/'manifest.json').read_text(encoding='utf-8'))
        if (cached_manifest.get('base_request_sha256')!=base_identity
                or any(cached_manifest.get(key)!=manifest[key] for key in ('artifact_hashes','contract_sha256','cache_key'))):
            raise ValueError('Automatic semantic cache identity mismatch')
        response=(cache_entry/'response.json').read_bytes()
        identity=cached_manifest['request_sha256']
        manifest=cached_manifest
        shutil.copyfile(cache_entry/'request.json',args.out/'request.json')
        shutil.copyfile(cache_entry/'manifest.json',args.out/'manifest.json')
        origin='cache'
    else:
        base=os.environ.get('LLM_JUDGE_BASE_URL')
        key=os.environ.get('LLM_JUDGE_API_KEY')
        if not base or not key:raise RuntimeError('Set LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY')
        endpoint=base.rstrip('/')
        if not endpoint.endswith('/v1/responses'):
            endpoint+=('/responses' if endpoint.endswith('/v1') else '/v1/responses')
        for protocol_attempt in range(3):
            wire=json.dumps(body,ensure_ascii=False,sort_keys=True).encode('utf-8')
            req=urllib.request.Request(endpoint,data=wire,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            for transport_attempt in range(3):
                try:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as stream:
                        response=json.dumps(json.loads(stream.read()),ensure_ascii=False).encode('utf-8')
                    break
                except urllib.error.HTTPError as error:
                    if transport_attempt==2 or error.code not in (429,500,502,503,504):raise
                    time.sleep(2)
            (args.out/f'response.attempt-{protocol_attempt+1}.json').write_bytes(response)
            try:
                parse_response(json.loads(response),evidence,contract)
                break
            except (ValueError,TypeError,KeyError) as error:
                if protocol_attempt==2:raise RuntimeError('Invalid semantic response protocol: '+str(error)) from error
                envelope=json.loads(response)
                messages=[c.get('text','') for o in envelope.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text' and c.get('text','').strip()]
                answer=messages[-1] if messages else ''
                correction=('Return the complete JSON object again and fix this protocol error: '+str(error)
                    +'. Every evidence quote must be a short exact contiguous substring copied from the cited evidence ID; never paraphrase a quote.')
                body['input'].extend([{'role':'assistant','content':answer},{'role':'user','content':correction}])
        raw=json.dumps(body,ensure_ascii=False,sort_keys=True).encode('utf-8')
        identity=hashlib.sha256(raw).hexdigest();manifest['request_sha256']=identity
        (args.out/'request.json').write_bytes(raw)
        (args.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.out/'response.json').write_bytes(response)
    envelope=json.loads(response);result=parse_response(envelope,evidence,contract)
    result.update(response_id=envelope.get('id'),model=envelope.get('model'),base_request_sha256=base_identity,
        request_sha256=identity,cache_key=cache_key,origin=origin,seconds=round(time.time()-start,2),
        fresh_call=origin=='live',visual_input=False)
    (args.out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if cache_entry and origin=='live':
        cache_entry.mkdir(parents=True,exist_ok=True)
        for name in ('request.json','response.json','manifest.json','review.json'):
            shutil.copyfile(args.out/name,cache_entry/name)
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
