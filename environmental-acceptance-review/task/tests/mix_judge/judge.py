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
from difflib import SequenceMatcher

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
    if path.suffix=='.docx':
        import sys
        sys.path.insert(0,str(HERE.parent))
        from read_word_comments import extract_docx
        doc=extract_docx(path)
        units=[dict(id=f'{prefix}-P{i}',text=('Preserved review draft, not endorsement: ' if '批注稿' in path.name else '')+x) for i,x in enumerate(doc['body_paragraphs'],1) if x.strip()]
        units += [dict(id=f"{prefix}-COMMENT-{c['id']}",text="Reviewer annotation anchored to ["+c['anchor']+"]: "+c['text']) for c in doc['comments']]
        return units
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
    missing=[name for name in contract.get('required_inputs',[]) if not (input_dir/name).is_file()]
    if missing:raise FileNotFoundError('Required source material missing: '+', '.join(missing))
    evidence=dict(candidate=[],workbook_sample=[],golden_meaning=[],source_materials=[],verified_facts=[])
    hashes={}
    for group,folder,prefix in [('candidate',submission,'C'),('golden_meaning',ROOT/'golden','G')]:
        for i,name in enumerate(contract['outputs'],1):
            p=folder/name
            evidence[group]+=extract(p,f'{prefix}{i}')
            hashes[group+'/'+name]=sha(p)
    for i,p in enumerate(sorted(p for p in input_dir.rglob('*') if not p.name.startswith('~$')),1):
        if p.is_file() and not p.name.startswith('~$'):
            units=extract(p,f'S{i}')
            if units:evidence['source_materials']+=units;hashes['source/'+p.relative_to(input_dir).as_posix()]=sha(p)
    fp=TASK_ROOT/'tests/reference/facts.json'
    evidence['verified_facts']=[dict(id='F1',text=fp.read_text(encoding='utf8'))];hashes['facts']=sha(fp)
    evidence['scope']='All supplied business document text and table rows. No visual assessment. Source evidence takes precedence over reference.'
    return evidence,hashes

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
    def partial_ratio(quote,text):
        quote=normalize(quote);text=normalize(text)
        if quote in text:return 1.0
        if not quote or not text:return 0.0
        low=max(1,len(quote)-2);high=min(len(text),len(quote)+2)
        return max((SequenceMatcher(None,quote,text[start:start+size]).ratio()
                    for size in range(low,high+1)
                    for start in range(0,len(text)-size+1)),default=0.0)
    for row in rows:
        if type(row.get('score')) not in (int,float) or row['score'] not in [0,0.5,1]:raise ValueError('Invalid criterion score')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():raise ValueError('Reason missing')
        citations=row.get('evidence')
        if not isinstance(citations,list) or not citations:raise ValueError('Evidence missing')
        for citation in citations:
            key=citation.get('id');quote=citation.get('quote')
            if key in units and not quote:
                citation['quote']=quote=units[key]
                citation['quote_origin']='runtime_exact_evidence_unit'
            if not isinstance(quote,str) or not normalize(quote):
                raise ValueError('Empty semantic evidence: '+str(key))
            if key not in units or normalize(quote) not in normalize(units[key]):
                # Preserve evidence class and accept only a near-verbatim local span.
                prefix=key[:1] if isinstance(key,str) else ''
                ranked=sorted(((partial_ratio(quote,text),unit_id) for unit_id,text in units.items()
                               if unit_id.startswith(prefix)),reverse=True)
                if not ranked or ranked[0][0]<0.96:raise ValueError('Unbound semantic evidence: '+str(key))
                citation['id']=key=ranked[0][1]
        if row['score']>0 and not any(c['id'].startswith(('C','W')) for c in citations):raise ValueError('Positive credit requires candidate evidence')
        if not any(c['id'].startswith(('G','S','F')) for c in citations):
            candidate_text='\n'.join(units[c['id']] for c in citations if c['id'] in units)
            references=[(SequenceMatcher(None,normalize(candidate_text),normalize(text)).ratio(),key,text)
                        for key,text in units.items() if key.startswith(('G','S','F'))]
            if not references:raise ValueError('Criterion requires reference or source evidence')
            _,key,text=max(references)
            citations.append({'id':key,'quote':text,'quote_origin':'runtime_reference_autobind'})
    passed=all(r['score']==1 for r in rows) and not result['reference_conflict']
    if result['passed']!=passed:raise ValueError('Overall verdict inconsistent with criteria')
    result['semantic_score']=None if result['reference_conflict'] else round(sum(expected[r['id']]['weight']*r['score'] for r in rows),6)
    result['measurement_status']='reference_conflict_requires_review' if result['reference_conflict'] else 'completed'
    return result


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
    text=prompt+'\nCriteria:\n'+json.dumps(contract['criteria'],ensure_ascii=False)+'\nEvidence:\n'+json.dumps(evidence,ensure_ascii=False)
    schema=json.loads((HERE/'response.schema.json').read_text(encoding='utf-8'))
    criteria_schema=schema['properties']['criteria']
    criteria_schema['minItems']=criteria_schema['maxItems']=len(contract['criteria'])
    criteria_schema['items']['properties']['id']['enum']=[row['id'] for row in contract['criteria']]
    evidence_ids=[row['id'] for group in ['candidate','workbook_sample','golden_meaning','source_materials','verified_facts'] for row in evidence[group]]
    schema['properties']['criteria']['items']['properties']['evidence']['items']['properties']['id']['enum']=evidence_ids
    body=dict(model=os.environ.get('LLM_JUDGE_MODEL',settings['model']),store=False,
        max_output_tokens=settings['max_output_tokens'],input=[dict(role='user',content=[dict(type='input_text',text=text)])],
        text={'format':{'type':'json_schema','name':'environmental_semantic_review','strict':True,'schema':schema}})
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'response.json').exists() and not args.replay:raise ValueError('Output already contains a response; choose a new output folder')
    raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
    (args.out/'request.json').write_bytes(raw)
    (args.out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.out/'manifest.json').write_text(json.dumps(dict(artifact_hashes=hashes,request_sha256=hashlib.sha256(raw).hexdigest(),
        rollout_executed=False,visual_input=False,contract_sha256=sha(HERE/'contract.json')),ensure_ascii=False,indent=2),encoding='utf-8')
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
        replay_dir=HERE.parent/'golden_replay'/hashlib.sha256(raw).hexdigest()
        prior_manifest=json.loads((replay_dir/'manifest.json').read_text(encoding='utf-8'))
        if prior_manifest.get('request_sha256')!=hashlib.sha256(raw).hexdigest() or prior_manifest.get('artifact_hashes')!=hashes:
            raise ValueError('No exact request-bound packaged replay')
        response=(replay_dir/'response.json').read_bytes()
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
