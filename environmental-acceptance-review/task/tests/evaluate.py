from pathlib import Path
import argparse,json,subprocess,sys,math,re
from read_word_comments import extract_docx
HERE=Path(__file__).resolve().parent;TASK=HERE.parent;PACKAGE=TASK.parent
def run(command,log):
    r=subprocess.run(command,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=900)
    log.write_text(r.stdout+'\n'+r.stderr,encoding='utf8');return r.returncode
def office_readability_errors(submission,names):
    # Dependency failures remain unavailable measurement, outside candidate parsing.
    from docx import Document
    from openpyxl import load_workbook
    from zipfile import ZipFile
    from xml.etree import ElementTree
    errors=[]
    for name in names:
        path=submission/name
        if path.suffix.lower() not in ('.docx','.xlsx'):continue
        try:
            with ZipFile(path) as archive:
                if archive.testzip() is not None:raise ValueError('Office archive CRC failure')
                for member in archive.namelist():
                    if member.endswith(('.xml','.rels')):
                        ElementTree.fromstring(archive.read(member))
            if path.suffix.lower()=='.docx':
                document=Document(path)
                if not any(p.text.strip() for p in document.paragraphs) and not any(t.rows for t in document.tables):
                    raise ValueError('No report text or table rows available for review')
                for paragraph in document.paragraphs:_=paragraph.text
                for table in document.tables:
                    for row in table.rows:
                        for cell in row.cells:_=cell.text
            else:
                workbook=load_workbook(path,data_only=False)
                try:
                    for sheet in workbook:
                        for row in sheet.iter_rows(values_only=True):pass
                finally:workbook.close()
        except Exception as error:
            errors.append({'file':name,'error':type(error).__name__+': '+str(error)})
    return errors
def laboratory_stack_derating(submission):
    report=extract_docx(submission/'一期工程验收监测报告表（批注稿）.docx')
    opinion=extract_docx(submission/'验收材料补充意见.docx')
    text='\n'.join([c['text'] for c in report.get('comments',[])]+opinion['body_paragraphs'])
    height='高度' in text
    action=any(token in text for token in ['核对','复核','重算','重新计算','适用限值计算'])
    conditional=any(token in text for token in ['50%','减半','折减','高度条件'])
    laboratory=('DA001' in text or 'DA010' in text or '实验室排气筒' in text)
    unit=bool(re.search(r'(?:14\s*kg\s*/?\s*h|14\s*(?:千克|公斤)\s*(?:每|/)\s*小时)', text, re.I))
    explicit=unit and height and action and laboratory
    return 1.0 if explicit else (0.5 if laboratory and height and conditional else 0.0)
def main():
    p=argparse.ArgumentParser();p.add_argument('--submission-dir',type=Path,default=Path('/workspace/output'));p.add_argument('--input',type=Path,default=TASK/'environment/workspace/input');p.add_argument('--out',type=Path,required=True);p.add_argument('--semantic-replay',type=Path);a=p.parse_args()
    out=a.out.resolve();submission=a.submission_dir.resolve()
    if out==PACKAGE or PACKAGE in out.parents or out==submission or submission in out.parents:raise SystemExit('Use an external result directory.')
    if out.exists() and any(out.iterdir()):raise SystemExit('Use a new result directory.')
    out.mkdir(parents=True,exist_ok=True)
    result={'status':'unmeasured','passed':False,'measurement_complete':False,'score':None,'rollout_executed':False}
    try:
        contract=json.loads((HERE/'mix_judge/contract.json').read_text(encoding='utf8'))
        missing_sources=[name for name in contract.get('required_inputs',[]) if not (a.input/name).is_file()]
        if missing_sources:raise FileNotFoundError('Required source material missing: '+', '.join(missing_sources))
        missing=[name for name in contract['outputs'] if not (submission/name).is_file() or not (submission/name).stat().st_size]
        artifact_errors=[] if missing else office_readability_errors(submission,contract['outputs'])
        if missing:
            result.update(status='submission_invalid',measurement_complete=True,score=0,missing=missing)
        elif artifact_errors:
            result.update(status='submission_invalid',measurement_complete=True,score=0,artifact_errors=artifact_errors)
        else:
            cmd=[sys.executable,'-B',str(HERE/'verify.py'),'--submission-dir',str(submission),'--input',str(a.input),'--out',str(out/'numeric.json')]
            code=run(cmd,out/'numeric-runtime.txt')
            if code not in (0,1):raise RuntimeError('Numeric execution failed')
            numeric=json.loads((out/'numeric.json').read_text(encoding='utf8'))
            if numeric.get('measurement_complete') is not True:raise RuntimeError('Numeric measurement unavailable')
            cmd=[sys.executable,'-B',str(HERE/'mix_judge/judge.py'),'--submission-dir',str(submission),'--input',str(a.input),'--out',str(out/'semantic')]
            if a.semantic_replay:cmd+=['--replay',str(a.semantic_replay)]
            if run(cmd,out/'semantic-runtime.txt')!=0:raise RuntimeError('Semantic measurement or bound replay unavailable')
            semantic=json.loads((out/'semantic/review.json').read_text(encoding='utf8'))
            if semantic.get('measurement_status')!='completed' or semantic.get('reference_conflict') is not False:raise RuntimeError('Semantic evidence conflict')
            for value in [numeric['score'],semantic['semantic_score']]:
                if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid score')
            params=json.loads((HERE/'scoring_params.json').read_text(encoding='utf8'))
            cells={'artifact_contract':numeric['score'],**{row['id']:row['score'] for row in semantic['criteria']}}
            cells['laboratory_stack_derating']=max(
                cells['laboratory_stack_derating'], laboratory_stack_derating(submission))
            owners={name:sum(cells[key] for key in spec['items'])/len(spec['items'])
                    for name,spec in params['owners'].items()}
            covered={key for spec in params['owners'].values() for key in spec['items']}
            if covered!=set(cells):raise ValueError('Scoring-cell coverage mismatch')
            if abs(sum(float(spec['weight']) for spec in params['owners'].values())-1)>1e-9:raise ValueError('Owner weights must sum to one')
            base=sum(float(params['owners'][name]['weight'])*score for name,score in owners.items())
            critical=sum(cells[key] for key in params['critical_controls'])/len(params['critical_controls'])
            strict=(2*base*critical/(base+critical)) if base+critical else 0.0
            minimum=float(params['lenient']['minimum_owner_score'])
            critical_minimum=float(params['lenient']['minimum_critical_control_score'])
            lenient=1.0 if (numeric['passed'] and min(owners.values())>=minimum and
                min(cells[key] for key in params['critical_controls'])>=critical_minimum) else 0.0
            result.update(status='completed',measurement_complete=True,business_measurement_complete=True,
                passed=numeric['passed'] and semantic['passed'],score=round(strict,12),reward_strict=round(strict,12),
                reward_lenient=lenient,base_score=round(base,12),owner_chains={},owner_damage=0.0,
                criterion_scores=cells,owner_scores=owners,critical_control_score=round(critical,12),
                lenient_minimum_owner=minimum,lenient_minimum_critical_control=critical_minimum,
                numeric_score=numeric['score'],
                semantic_score=semantic['semantic_score'],semantic_fresh_call=semantic['fresh_call'])
    except Exception as e:result['measurement_error']=type(e).__name__+': '+str(e)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
    return 0 if result['passed'] else (2 if result['status']=='unmeasured' else 1)
if __name__=='__main__':raise SystemExit(main())
