"""Evaluate the published submission filenames; never award numeric-only mixed credit."""
from pathlib import Path
import argparse,json,math,subprocess,sys
from zipfile import BadZipFile

HERE=Path(__file__).resolve().parent
TASK=Path('/task') if Path('/task/instruction.md').is_file() else HERE.parent
PACKAGE=TASK.parent
CONFIG={'complete_field':'measurement_complete','score_field':'score','score_scale':1,'input_file':None}

class MeasurementUnavailable(Exception):pass

def finite_number(value,label,lower=0,upper=1):
    if type(value) not in (int,float) or not math.isfinite(value) or not lower<=value<=upper:
        raise MeasurementUnavailable(label+' must be a finite number in the documented range')
    return float(value)

def submission_files(directory):
    directory=Path(directory);wb=directory/'维修询价清单.xlsx';report=directory/'施工范围说明.docx'
    errors=[]
    for path in [wb,report]:
        if not path.is_file() or path.stat().st_size==0:errors.append('Provide a nonempty '+path.name)
    return wb,report,errors

def validate_formats(workbook,report):
    from openpyxl import load_workbook
    from docx import Document
    errors=[]
    try:
        w=load_workbook(workbook,read_only=True,data_only=True);w.close()
        d=Document(report)
        if not any(p.text.strip() for p in d.paragraphs) and not d.tables:errors.append('Scope note has no extractable text')
    except PermissionError:raise
    except Exception as exc:errors.append('Unreadable submitted business file: '+type(exc).__name__)
    return errors


def normalized_numeric(raw):
    if not isinstance(raw,dict):raise MeasurementUnavailable('Numeric receipt is not an object')
    flag=raw.get(CONFIG['complete_field'])
    if type(flag) is not bool or not flag:raise MeasurementUnavailable('Numeric measurement incomplete')
    if type(raw.get('passed')) is not bool:raise MeasurementUnavailable('Numeric verdict is not Boolean')
    value=finite_number(raw.get(CONFIG['score_field']),'numeric score',0,CONFIG['score_scale'])/CONFIG['score_scale']
    return {'score':value,'passed':raw['passed'],'checks':raw.get('checks')}

def normalized_semantic(raw):
    if not isinstance(raw,dict) or raw.get('measurement_status')!='completed':raise MeasurementUnavailable('Semantic measurement incomplete or reference conflict')
    if type(raw.get('passed')) is not bool:raise MeasurementUnavailable('Semantic verdict is not Boolean')
    if raw.get('reference_conflict') is not False:raise MeasurementUnavailable('Semantic reference-conflict flag must be false')
    value=finite_number(raw.get('semantic_score'),'semantic score')
    rows=raw.get('criteria')
    if not isinstance(rows,list):raise MeasurementUnavailable('Semantic criterion rows missing')
    criteria={}
    for row in rows:
        identifier=row.get('id');completion=row.get('score')
        if not isinstance(identifier,str) or identifier in criteria:raise MeasurementUnavailable('Semantic criterion IDs invalid')
        criteria[identifier]=finite_number(completion,'semantic completion')
    return {'score':value,'passed':raw['passed'],'fresh_call':raw.get('fresh_call'),'criteria':criteria}

def combine(numeric,semantic,params):
    n=normalized_numeric(numeric);s=normalized_semantic(semantic)
    owner_map=params.get('numeric_owner_map')
    if not isinstance(owner_map,dict):raise MeasurementUnavailable('Scoring parameters incomplete')
    completions={}
    if isinstance(n['checks'],dict):
        for item,owner in owner_map.items():
            detail=n['checks'].get(owner)
            if not isinstance(detail,dict):raise MeasurementUnavailable('Numeric owner missing: '+item)
            completions[item]=finite_number(detail.get('score'),'numeric owner completion')
    elif n['score']==0:
        completions.update({item:0.0 for item in owner_map})
    else:raise MeasurementUnavailable('Numeric owner detail unavailable')
    completions.update(s['criteria'])
    closures=params.get('closures')
    if not isinstance(closures,dict) or abs(sum(row['weight'] for row in closures.values())-1)>1e-8:raise MeasurementUnavailable('Local closure weights must sum to one')
    expected_owners={owner for row in closures.values() for owner in row['owners']}
    if set(completions)!=expected_owners:raise MeasurementUnavailable('Owner coverage does not match scoring parameters')
    closure_values={}
    for key,row in closures.items():
        values=[completions[owner] for owner in row['owners']]
        closure_values[key]=math.prod(values) if row['operator']=='product' else sum(values)/len(values)
    strict=sum(closures[key]['weight']*value for key,value in closure_values.items())
    must_have=params.get('lenient_policy',{}).get('must_have')
    if not isinstance(must_have,dict):raise MeasurementUnavailable('Lenient must-have policy missing')
    verdicts={};failed={}
    for item,owners in must_have.items():
        if not isinstance(owners,list) or any(owner not in completions for owner in owners):
            raise MeasurementUnavailable('Lenient owner mapping invalid: '+item)
        failed[item]=[owner for owner in owners if completions[owner]!=1]
        verdicts[item]=int(not failed[item])
    lenient=int(all(verdicts.values()))
    return {'status':'completed','passed':strict==1 and lenient==1,'measurement_complete':True,'business_measurement_complete':True,
            'score':strict,'rewards':{'strict':strict,'lenient':lenient},'strict_score':strict,'lenient_score':lenient,
            'closure_values':closure_values,'closure_parameters':closures,
            'owner_completions':completions,
            'lenient_evaluation':{'verdicts':verdicts,'failed_owners':failed},
            'numeric_score':n['score'],'semantic_score':s['score'],'semantic_fresh_call':s['fresh_call'],'rollout_executed':False}

def run_command(command,log,timeout):
    try:
        p=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        log.write_text('Runtime timeout.\n',encoding='utf8');raise MeasurementUnavailable('Evaluation subprocess timed out') from exc
    log.write_text(p.stdout+'\n'+p.stderr,encoding='utf8');return p.returncode

def read_receipt(path):
    try:return json.loads(path.read_text(encoding='utf8'))
    except (OSError,ValueError) as exc:raise MeasurementUnavailable('Missing or malformed runtime receipt: '+path.name) from exc

def evaluate(submission_dir,input_path,out,semantic_replay=None,timeout=900):
    wb,report,errors=submission_files(submission_dir)
    if not errors:errors=validate_formats(wb,report)
    if errors:
        return {'status':'submission_invalid','passed':False,'measurement_complete':True,'business_measurement_complete':False,
                'score':0.0,'rewards':{'strict':0.0,'lenient':0},'strict_score':0.0,'lenient_score':0,
                'numeric_score':None,'semantic_score':None,'submission_errors':errors,
                'lenient_evaluation':{'verdicts':{'published_files':0},'failed_owners':{'published_files':['published_files']}},
                'scope':'The published file contract failed. Business checks and semantic review were not run.','rollout_executed':False}
    params=read_receipt(HERE/'scoring_params.json')
    public_input=Path(input_path)
    if CONFIG['input_file']:
        numeric_input=public_input if public_input.is_file() else public_input/CONFIG['input_file']
        semantic_input=numeric_input.parent
    else:numeric_input=public_input;semantic_input=public_input
    if not numeric_input.exists() or not semantic_input.is_dir():raise MeasurementUnavailable('Author-supplied input materials unavailable')
    command=[sys.executable,'-B',str(HERE/'verify.py'),'--workbook',str(wb),'--input',str(numeric_input),'--report',str(out/'numeric.json')]
    code=run_command(command,out/'numeric-runtime.txt',timeout)
    if code not in (0,1):raise MeasurementUnavailable('Numeric verifier failed to execute normally')
    numeric=read_receipt(out/'numeric.json')
    normalized_numeric(numeric)
    judge=HERE/'mix_judge/judge.py'
    if not judge.is_file():raise MeasurementUnavailable('Required semantic judge runtime is unavailable')
    command=[sys.executable,'-B',str(judge),'--report',str(report),'--workbook',str(wb),'--input',str(semantic_input),'--out',str(out/'semantic')]
    if semantic_replay:command.extend(['--replay',str(semantic_replay)])
    code=run_command(command,out/'semantic-runtime.txt',timeout)
    if code!=0:raise MeasurementUnavailable('Semantic runtime or request-bound replay failed')
    semantic=read_receipt(out/'semantic/review.json')
    result=combine(numeric,semantic,params)
    result['scope']='Published submission contract, independent workbook checks and content-only semantic review. No visual score or container qualification implied.'
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--submission-dir',type=Path,default=Path('/workspace/output'))
    p.add_argument('--input',type=Path,default=Path('/workspace/input') if Path('/workspace/input').is_dir() else TASK/'environment/workspace/input')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--semantic-replay',type=Path,help='Author replay of an original response.json; judge checks the complete request hash')
    p.add_argument('--timeout-sec',type=int,default=900)
    a=p.parse_args();writable=False
    try:
        target=a.out.resolve();submission=a.submission_dir.resolve()
        # In the published container TASK is /task and PACKAGE is the filesystem
        # root because Golden is mounted at /golden.  Only enforce the package
        # write guard when PACKAGE names an actual package directory.
        package_guard=PACKAGE.resolve() if TASK.name=='task' and PACKAGE.resolve()!=Path('/') else None
        if (package_guard is not None and (target==package_guard or package_guard in target.parents)) or target==submission or submission in target.parents:
            raise MeasurementUnavailable('Evaluation output must be outside the task package and submission directory')
        if a.timeout_sec<=0:raise MeasurementUnavailable('Timeout must be positive')
        if target.exists() and not target.is_dir():raise MeasurementUnavailable('Evaluation output path is not a directory')
        target.mkdir(parents=True,exist_ok=True);writable=True
        if any(target.iterdir()):raise MeasurementUnavailable('Choose an empty external evaluation directory; existing evidence will not be overwritten')
        result=evaluate(submission,a.input.resolve(),target,a.semantic_replay.resolve() if a.semantic_replay else None,a.timeout_sec)
    except Exception as exc:
        result={'status':'unmeasured','passed':False,'measurement_complete':False,'business_measurement_complete':False,'score':None,
                'numeric_score':None,'semantic_score':None,'measurement_error':type(exc).__name__+': '+str(exc),'rollout_executed':False}
        if writable and (a.out/'numeric.json').is_file():
            try:result['numeric_score']=normalized_numeric(read_receipt(a.out/'numeric.json'))['score']
            except Exception:pass
    if writable:(a.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 0 if result['passed'] else (2 if result['status']=='unmeasured' else 1)

if __name__=='__main__':raise SystemExit(main())
