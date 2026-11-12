from pathlib import Path
import hashlib
import argparse,csv,html,json,re,subprocess,sys,math
HERE=Path(__file__).resolve().parent
TASK=Path('/task') if Path('/task/instruction.md').is_file() else HERE.parent
PACKAGE=TASK.parent
def run(command,log):
    r=subprocess.run(command,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=900)
    log.write_text(r.stdout+'\n'+r.stderr,encoding='utf8');return r.returncode
def office_readability_errors(submission,names):
    # Dependency failures remain unavailable measurement, outside candidate parsing.
    from docx import Document
    from openpyxl import load_workbook
    from zipfile import ZipFile
    from xml.etree import ElementTree
    import csv
    errors=[]
    for name in names:
        path=submission/name
        if path.suffix.lower()=='.csv':
            try:
                with path.open(encoding='utf-8-sig',newline='') as stream:
                    for row in csv.reader(stream,strict=True):pass
            except (UnicodeError,csv.Error,OSError) as error:
                errors.append({'file':name,'error':type(error).__name__+': '+str(error)})
            continue
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
def clean_copy(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip().lower()
def explains_pack_contents(value):
    text=clean_copy(value);one=bool(re.search(r'(?:1[- ]?pack|single chair).{0,100}(?:one|1|single) (?:chair|lounger)',text));two=bool(re.search(r'2[- ]?pack.{0,100}(?:two|2)(?: (?:chairs|loungers))?',text))
    return (one and two) or 'selected pack size is the number of chairs supplied' in text or ('one chair' in text and 'two chairs' in text) or ('single chair' in text and 'two-chair pack' in text)
def page_pack_flags(submission):
    facts=json.loads((HERE/'reference/facts.json').read_text(encoding='utf8'));expected={row['sku']:row for row in facts['rows']};descriptions={}
    with (submission/'products.csv').open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            source=expected.get(row.get('SKU',''))
            if source and row.get('Title') and row.get('Description'):descriptions[source['series']]=row['Description']
    return {series:explains_pack_contents(descriptions.get(series,'')) for series in ['C01','C02','C03','C06','C08','C10']}
def main():
    p=argparse.ArgumentParser();p.add_argument('--submission-dir',type=Path,default=Path('/workspace/output'));p.add_argument('--input',type=Path,default=TASK/'environment/workspace/input');p.add_argument('--out',type=Path,required=True);p.add_argument('--semantic-replay',type=Path);a=p.parse_args()
    out=a.out.resolve();submission=a.submission_dir.resolve()
    protected=[submission]
    # In the standard verifier image TASK is /task and PACKAGE is the
    # filesystem root, while the Golden is mounted at /golden.  The root must
    # not be treated as a protected package directory or every /logs receipt
    # would be rejected.
    if PACKAGE != Path('/'):
        protected.append(PACKAGE)
    if any(out==root or root in out.parents for root in protected):raise SystemExit('Use an external result directory.')
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
            replay=a.semantic_replay
            if replay:cmd+=['--replay',str(replay)]
            if run(cmd,out/'semantic-runtime.txt')!=0:raise RuntimeError('Semantic measurement or bound replay unavailable')
            semantic=json.loads((out/'semantic/review.json').read_text(encoding='utf8'))
            if semantic.get('measurement_status')!='completed' or semantic.get('reference_conflict') is not False:raise RuntimeError('Semantic evidence conflict')
            for value in [numeric['score'],semantic['semantic_score']]:
                if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid score')
            
            by_id={row['id']:row['score'] for row in semantic['criteria']};packs=page_pack_flags(submission)
            # Pack-page release uses the measured partial-credit owners rather
            # than turning a 0.5 semantic finding into a hidden binary gate.
            # The page-specific pack flag still requires explicit one-chair /
            # two-chair customer copy on that page.
            local=[float(packs['C01'])*by_id['measurement_item_scope']*by_id['measurement_state_scope'],
                   float(packs['C02'])*by_id['measurement_item_scope']*by_id['measurement_state_scope'],
                   float(packs['C03'])*by_id['measurement_item_scope']*by_id['measurement_state_scope']*by_id['measurement_load_scope'],
                   float(packs['C06'])*by_id['measurement_item_scope']*by_id['measurement_state_scope'],
                   float(packs['C08'])*by_id['measurement_item_scope']*by_id['measurement_state_scope']*by_id['measurement_load_scope'],
                   float(packs['C10'])*by_id['measurement_item_scope']*by_id['measurement_load_scope']]
            claims=[by_id[k] for k in ['claims_c01_c02','claims_c03_c04','claims_c05_c06','claims_c07_c08','claims_c09_c10']]
            pack_page={1:0,2:1,3:2,6:3,8:4,10:5}
            measurement_mean=sum(by_id[key] for key in ['measurement_item_scope','measurement_state_scope','measurement_load_scope'])/3
            page_release={}
            for page in range(1,11):
                claim=claims[(page-1)//2]
                scope=local[pack_page[page]] if page in pack_page else measurement_mean
                page_release[f'C{page:02d}']=by_id['product_identity']*claim*scope
            page_release_mean=sum(page_release.values())/len(page_release)
            score=numeric['score']*page_release_mean
            score=round(score,12)
            # A usable handoff must establish the factual catalog core as well
            # as clear the aggregate floor.  A partial page/claim result alone
            # must not turn into lenient=1 while SKU, price or grouping checks
            # are still wrong.
            core_numeric = all(numeric.get('checks', {}).get(key) is True
                               for key in ('schema', 'range', 'grouping', 'options', 'prices', 'staging'))
            core_semantic = by_id.get('product_identity') == 1
            core_content = (numeric.get('checks', {}).get('content_structure') is True
                and by_id.get('physical_sales_unit') == 1
                and all(value >= .5 for value in claims))
            lenient = float(core_numeric and core_semantic and core_content)
            result.update(status='completed',measurement_complete=True,business_measurement_complete=True,passed=score==1,score=score,reward_strict=score,reward_lenient=lenient,rewards={'strict':score,'lenient':lenient},numeric_score=numeric['score'],semantic_score=semantic['semantic_score'],page_release=page_release,page_release_mean=page_release_mean,local_page_diagnostics=local,semantic_fresh_call=semantic['fresh_call'])
    except Exception as e:result['measurement_error']=type(e).__name__+': '+str(e)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
    return 0 if result['passed'] else (2 if result['status']=='unmeasured' else 1)
if __name__=='__main__':raise SystemExit(main())
