"""Evaluate the published submission filenames; never award numeric-only mixed credit."""
from pathlib import Path
import argparse,json,math,subprocess,sys
from zipfile import BadZipFile

HERE=Path(__file__).resolve().parent
TASK=next((path for path in (HERE.parent,Path('/task'),HERE) if (path/'rubric.json').is_file()),HERE.parent)
PACKAGE=TASK.parent if TASK.name=='task' and TASK.parent!=Path('/') else TASK
CONFIG={'complete_field': 'measurement_complete', 'score_field': 'score', 'score_scale': 1, 'input_file': None}

class MeasurementUnavailable(Exception):pass

def finite_number(value,label,lower=0,upper=1):
    if type(value) not in (int,float) or not math.isfinite(value) or not lower<=value<=upper:
        raise MeasurementUnavailable(label+' must be a finite number in the documented range')
    return float(value)

def submission_files(directory):
    directory=Path(directory);results=directory/'review-results.json';readme=directory/'measurement-check/README.md'
    required=[results,readme,directory/'measurement-check/measurement_check.py',directory/'exceptions.csv']
    errors=['Provide a nonempty '+str(p.relative_to(directory)) for p in required if not p.is_file() or p.stat().st_size==0]
    return results,readme,errors

def validate_formats(results,readme):
    errors=[]
    try:
        def bad(value):raise ValueError('Nonfinite JSON constant')
        value=json.loads(results.read_text(encoding='utf-8-sig'),parse_constant=bad)
        if not isinstance(value,dict):errors.append('review-results.json must be an object')
        if not readme.read_text(encoding='utf-8-sig').strip():errors.append('README.md is empty')
    except PermissionError:raise
    except (ValueError,UnicodeError,OSError) as exc:errors.append('Unreadable JSON or README: '+type(exc).__name__)
    return errors

def normalized_numeric(raw):
    if not isinstance(raw,dict):raise MeasurementUnavailable('Numeric receipt is not an object')
    flag=raw.get(CONFIG['complete_field'])
    if type(flag) is not bool or not flag:raise MeasurementUnavailable('Numeric measurement incomplete')
    if type(raw.get('passed')) is not bool:raise MeasurementUnavailable('Numeric verdict is not Boolean')
    value=finite_number(raw.get(CONFIG['score_field']),'numeric score',0,CONFIG['score_scale'])/CONFIG['score_scale']
    owners=raw.get('owners')
    if not isinstance(owners,dict):raise MeasurementUnavailable('Numeric owner ledger is missing')
    owners={key:finite_number(item,'numeric owner '+key) for key,item in owners.items()}
    completion=raw.get('completion')
    required={'delivered_contract','fresh_cli','result_coverage'}
    if not isinstance(completion,dict) or set(completion)!=required or any(type(v) is not bool for v in completion.values()):
        raise MeasurementUnavailable('Independent numeric completion decisions are missing')
    return {'score':value,'passed':raw['passed'],'owners':owners,'completion':completion}

def normalized_semantic(raw):
    if not isinstance(raw,dict) or raw.get('measurement_status')!='completed':raise MeasurementUnavailable('Semantic measurement incomplete or reference conflict')
    if type(raw.get('passed')) is not bool:raise MeasurementUnavailable('Semantic verdict is not Boolean')
    if raw.get('reference_conflict') is not False:raise MeasurementUnavailable('Semantic reference-conflict flag must be false')
    value=finite_number(raw.get('semantic_score'),'semantic score')
    criteria=raw.get('criteria')
    if not isinstance(criteria,list):raise MeasurementUnavailable('Semantic criterion ledger is missing')
    measured={row.get('id'):finite_number(row.get('score'),'semantic criterion '+str(row.get('id')))
              for row in criteria if isinstance(row,dict)}
    required={'conclusion','evidence','tradeoffs','scope'}
    if set(measured)!=required:raise MeasurementUnavailable('Semantic criterion ledger does not match the contract')
    completion=raw.get('completion')
    if not isinstance(completion,dict) or set(completion)!=required or any(type(v) is not bool for v in completion.values()):
        raise MeasurementUnavailable('Independent semantic completion decisions are missing')
    return {'score':value,'passed':raw['passed'],'fresh_call':raw.get('fresh_call'),'criteria':measured,'completion':completion}

def combine(numeric,semantic):
    n=normalized_numeric(numeric);s=normalized_semantic(semantic)
    params=json.loads((HERE/'strict-params.json').read_text(encoding='utf8'))
    diagnostic_ids=set(params.get('diagnostic_owners',[]))
    diagnostics={key:value for key,value in n['owners'].items() if key in diagnostic_ids}
    completions={key:value for key,value in n['owners'].items() if key not in diagnostic_ids}
    completions.update({'S_'+key.upper():value for key,value in s['criteria'].items()})
    direct=params.get('direct_weights');chains=params.get('chains')
    reference=params.get('reference_owner_weights')
    if not isinstance(direct,dict) or set(direct)!=set(completions):
        raise MeasurementUnavailable('Every measured owner must have direct strict credit')
    if not isinstance(chains,dict) or not chains:
        raise MeasurementUnavailable('Local dependency policy is missing')
    if not isinstance(reference,dict) or set(reference)!=set(completions):
        raise MeasurementUnavailable('Reference owner weights do not match the scored ledger')
    direct={key:finite_number(value,'direct weight '+key) for key,value in direct.items()}
    reference={key:finite_number(value,'reference weight '+key) for key,value in reference.items()}
    if any(value<=0 for value in direct.values()) or abs(sum(reference.values())-1)>1e-8:
        raise MeasurementUnavailable('Direct weights must be positive and reference weights must sum to one')
    chain_values={};chain_weights={};chain_details={}
    for identifier,item in chains.items():
        if not isinstance(item,dict) or item.get('operator') not in {'product','min'}:
            raise MeasurementUnavailable('Unsupported local dependency '+identifier)
        owners=item.get('owners')
        if not isinstance(owners,list) or not owners or len(set(owners))!=len(owners) or not set(owners)<=set(completions):
            raise MeasurementUnavailable('Malformed local dependency '+identifier)
        weight=finite_number(item.get('weight'),'dependency weight '+identifier)
        values=[completions[owner] for owner in owners]
        value=math.prod(values) if item['operator']=='product' else min(values)
        chain_values[identifier]=value;chain_weights[identifier]=weight
        chain_details[identifier]={'operator':item['operator'],'owners':owners,
                                   'completion':value,'weight':weight}
    if abs(sum(direct.values())+sum(chain_weights.values())-1)>1e-8:
        raise MeasurementUnavailable('Direct and local dependency weights must sum to one')
    direct_credit=sum(direct[key]*value for key,value in completions.items())
    chain_credit=sum(chain_weights[key]*value for key,value in chain_values.items())
    minimum_damage=finite_number(params.get('minimum_completion_damage'),'minimum completion damage')
    minimum_completion_passed=all(n['completion'].values())
    completion_damage=0.0 if minimum_completion_passed else minimum_damage
    score=max(0.0,direct_credit+chain_credit-completion_damage)
    raw_owner_completion=sum(reference[key]*value for key,value in completions.items())
    scoring=json.loads((HERE/'scoring_params.json').read_text(encoding='utf8'))
    policy=scoring.get('lenient',{})
    if not policy.get('numeric_completion_required') or not policy.get('semantic_required'):
        raise MeasurementUnavailable('Lenient must-have policy is missing')
    lenient_decisions={key:n['completion'].get(key,False) for key in policy['numeric_completion_required']}
    lenient_decisions.update({'semantic_'+key:s['completion'].get(key,False) for key in policy['semantic_required']})
    lenient=float(all(lenient_decisions.values()))
    return {'status':'completed','passed':all(value==1 for value in completions.values()),
            'measurement_complete':True,'business_measurement_complete':True,
            'score':round(score,12),'reward':round(score,12),
            'rewards':{'strict':round(score,12),'lenient':lenient},
            'strict_settlement':'local-conjunctive-additive',
            'strict_raw_owner_completion':raw_owner_completion,
            'strict_direct_credit':direct_credit,'strict_chain_credit':chain_credit,
            'minimum_completion_damage':completion_damage,
            'strict_components':chain_details,
            'owner_completions':completions,'owner_direct_weights':direct,
            'reference_owner_weights':reference,'diagnostic_completions':diagnostics,
            'lenient_evaluation':{'must_have':lenient_decisions,
                'failed_ids':[key for key,value in lenient_decisions.items() if not value]},
            'numeric_score':n['score'],'semantic_score':s['score'],
            'semantic_fresh_call':s['fresh_call']}

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
                'score':0.0,'reward':0.0,'rewards':{'strict':0.0,'lenient':0.0},
                'numeric_score':None,'semantic_score':None,'submission_errors':errors,
                'scope':'The published file contract failed. Business checks and semantic review were not run.'}
    public_input=Path(input_path)
    if CONFIG['input_file']:
        numeric_input=public_input if public_input.is_file() else public_input/CONFIG['input_file']
        semantic_input=numeric_input.parent
    else:numeric_input=public_input;semantic_input=public_input
    if not numeric_input.exists() or not semantic_input.is_dir():raise MeasurementUnavailable('Author-supplied input materials unavailable')
    command=[sys.executable,'-B',str(HERE/'verify_v2.py'),'--submission-dir',str(submission_dir),'--input',str(numeric_input),'--report',str(out/'numeric.json')]
    code=run_command(command,out/'numeric-runtime.txt',timeout)
    if code not in (0,1):raise MeasurementUnavailable('Numeric verifier failed to execute normally')
    numeric=read_receipt(out/'numeric.json')
    normalized_numeric(numeric)
    judge=HERE/'mix_judge/judge.py'
    if not judge.is_file():raise MeasurementUnavailable('Required semantic judge runtime is unavailable')
    command=[sys.executable,'-B',str(judge),'--results',str(wb),'--readme',str(report),'--input',str(semantic_input),'--out',str(out/'semantic')]
    if semantic_replay:command.extend(['--replay',str(semantic_replay)])
    code=run_command(command,out/'semantic-runtime.txt',timeout)
    if code!=0:raise MeasurementUnavailable('Semantic runtime or request-bound replay failed')
    semantic=read_receipt(out/'semantic/review.json')
    result=combine(numeric,semantic)
    result['scope']='Published submission contract, independent CLI and JSON/CSV checks and content-only semantic review. No visual score or container qualification implied.'
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
        if target==PACKAGE.resolve() or PACKAGE.resolve() in target.parents or target==submission or submission in target.parents:
            raise MeasurementUnavailable('Evaluation output must be outside the task package and submission directory')
        if a.timeout_sec<=0:raise MeasurementUnavailable('Timeout must be positive')
        if target.exists() and (not target.is_dir() or any(target.iterdir())):raise MeasurementUnavailable('Choose an empty external evaluation directory; existing evidence will not be overwritten')
        target.mkdir(parents=True,exist_ok=True);writable=True
        result=evaluate(submission,a.input.resolve(),target,a.semantic_replay.resolve() if a.semantic_replay else None,a.timeout_sec)
    except Exception as exc:
        result={'status':'unmeasured','passed':False,'measurement_complete':False,'business_measurement_complete':False,'score':None,
                'numeric_score':None,'semantic_score':None,'measurement_error':type(exc).__name__+': '+str(exc)}
        if writable and (a.out/'numeric.json').is_file():
            try:result['numeric_score']=normalized_numeric(read_receipt(a.out/'numeric.json'))['score']
            except Exception:pass
    if writable:(a.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 2 if result['status']=='unmeasured' else 0

if __name__=='__main__':raise SystemExit(main())
