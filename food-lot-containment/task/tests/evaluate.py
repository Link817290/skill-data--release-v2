"""Evaluate the published submission filenames; never award numeric-only mixed credit."""
from pathlib import Path
import argparse,json,math,subprocess,sys
from zipfile import BadZipFile

HERE=Path(__file__).resolve().parent
TASK=HERE.parent
PACKAGE=TASK
CONFIG={'complete_field': 'measurement_complete', 'score_field': 'score', 'score_scale': 1, 'input_file': None}

class MeasurementUnavailable(Exception):pass

def finite_number(value,label,lower=0,upper=1):
    if type(value) not in (int,float) or not math.isfinite(value) or not lower<=value<=upper:
        raise MeasurementUnavailable(label+' must be a finite number in the documented range')
    return float(value)

def scoring_params():
    raw=json.loads((HERE/'scoring_params.json').read_text(encoding='utf8'))
    chains=raw.get('strict',{}).get('chains',{})
    if not isinstance(chains,dict) or not chains:raise MeasurementUnavailable('Strict local chains are missing')
    weights=[]
    for identifier,chain in chains.items():
        if chain.get('operator') not in {'min','product','identity'}:raise MeasurementUnavailable('Unknown chain operator: '+identifier)
        weight=chain.get('weight');sources=chain.get('source_ids')
        if type(weight) not in (int,float) or weight<0:raise MeasurementUnavailable('Invalid chain weight: '+identifier)
        if not isinstance(sources,list) or not sources or any(not isinstance(x,str) or not x for x in sources):
            raise MeasurementUnavailable('Invalid chain sources: '+identifier)
        if chain['operator']=='identity' and len(sources)!=1:raise MeasurementUnavailable('Identity chain must have one source')
        weights.append(weight)
    if abs(sum(weights)-1)>1e-8:raise MeasurementUnavailable('Strict chain weights must sum to one')
    fatals=raw['strict'].get('fatal_errors',{})
    if not isinstance(fatals,dict):raise MeasurementUnavailable('Fatal-error policy is invalid')
    for identifier,rule in fatals.items():
        if rule.get('operator')!='all_zero' or not isinstance(rule.get('source_ids'),list):
            raise MeasurementUnavailable('Invalid fatal-error rule: '+identifier)
        finite_number(rule.get('score'),'fatal-error score')
    must=raw.get('lenient',{}).get('must_have',{})
    if not isinstance(must,dict) or not must:raise MeasurementUnavailable('Lenient must-have policy is missing')
    return raw

def submission_files(directory):
    directory=Path(directory);errors=[]
    for name in ['product-scope.csv','pack-changes.csv','distribution-list.csv']:
        path=directory/name
        if not path.is_file() or path.stat().st_size==0:errors.append('Provide a nonempty '+name)
    reports=[directory/('trade-recall-notice'+suffix) for suffix in ['.pdf','.docx']]
    reports=[p for p in reports if p.exists()]
    if len(reports)!=1:errors.append('Provide exactly one trade-recall-notice.pdf OR trade-recall-notice.docx.')
    report=reports[0] if len(reports)==1 else None
    if report is not None and (not report.is_file() or report.stat().st_size==0):errors.append('The notice must be a nonempty file.')
    prep=directory/'preparation'
    if not prep.is_dir():errors.append('Provide preparation/ with reproducible steps and documentation.')
    else:
        for name in ('build_registers.py','README.md'):
            path=prep/name
            if not path.is_file() or path.stat().st_size==0:errors.append('Provide nonempty preparation/'+name+'.')
    return directory,report,errors

def validate_formats(registers,report):
    from docx import Document
    import fitz,csv
    errors=[]
    for name in ['product-scope.csv','pack-changes.csv','distribution-list.csv']:
        try:
            with (registers/name).open(encoding='utf-8-sig',newline='') as stream:list(csv.reader(stream,strict=True))
        except PermissionError:raise
        except (UnicodeError,csv.Error,OSError) as exc:errors.append(name+' is not readable UTF-8 CSV: '+type(exc).__name__)
    try:
        if report.suffix=='.docx':Document(report)
        else:
            with fitz.open(report) as doc:
                if not doc.page_count or doc.needs_pass:errors.append('The notice PDF is empty or password protected.')
    except PermissionError:raise
    except Exception as exc:
        if isinstance(exc,ImportError):raise
        errors.append('The notice cannot be opened: '+type(exc).__name__)
    return errors

def normalized_numeric(raw):
    if not isinstance(raw,dict):raise MeasurementUnavailable('Numeric receipt is not an object')
    flag=raw.get(CONFIG['complete_field'])
    if type(flag) is not bool or not flag:raise MeasurementUnavailable('Numeric measurement incomplete')
    if type(raw.get('passed')) is not bool:raise MeasurementUnavailable('Numeric verdict is not Boolean')
    value=finite_number(raw.get(CONFIG['score_field']),'numeric score',0,CONFIG['score_scale'])/CONFIG['score_scale']
    return {'score':value,'passed':raw['passed']}

def normalized_semantic(raw):
    if not isinstance(raw,dict) or raw.get('measurement_status')!='completed':raise MeasurementUnavailable('Semantic measurement incomplete or reference conflict')
    if type(raw.get('passed')) is not bool:raise MeasurementUnavailable('Semantic verdict is not Boolean')
    if raw.get('reference_conflict') is not False:raise MeasurementUnavailable('Semantic reference-conflict flag must be false')
    value=finite_number(raw.get('semantic_score'),'semantic score')
    return {'score':value,'passed':raw['passed'],'fresh_call':raw.get('fresh_call')}

def chain_value(chain,completion):
    values=[completion[key] for key in chain['source_ids']]
    if chain['operator']=='min':return min(values)
    if chain['operator']=='product':return math.prod(values)
    return values[0]

def combine(numeric,semantic,params=None):
    n=normalized_numeric(numeric);s=normalized_semantic(semantic);params=params or scoring_params()
    numeric_rows=numeric.get('checks');semantic_rows=semantic.get('criteria')
    if not isinstance(numeric_rows,list) or not isinstance(semantic_rows,list):
        raise MeasurementUnavailable('Atomic numeric and semantic decisions are required')
    completion={row.get('id'):finite_number(row.get('score'),'numeric item score') for row in numeric_rows}
    for row in semantic_rows:
        identifier=row.get('id')
        if identifier in completion:raise MeasurementUnavailable('Duplicate atomic item ID')
        completion[identifier]=finite_number(row.get('score'),'semantic item score')
    chains=params['strict']['chains'];chain_sources={key for chain in chains.values() for key in chain['source_ids']}
    fatal_sources={key for rule in params['strict']['fatal_errors'].values() for key in rule['source_ids']}
    must_sources={item['source_id'] for item in params['lenient']['must_have'].values()}
    if set(completion)!=chain_sources|fatal_sources|must_sources:
        raise MeasurementUnavailable('Atomic item vocabulary differs from scoring parameters')
    chain_scores={key:chain_value(chain,completion) for key,chain in chains.items()}
    raw_chain_scores={key:sum(completion[source] for source in chain['source_ids'])/len(chain['source_ids'])
                      for key,chain in chains.items()}
    raw_credit=sum(chain['weight']*raw_chain_scores[key] for key,chain in chains.items())
    strict=sum(chain['weight']*chain_scores[key] for key,chain in chains.items())
    fatal_decisions={key:all(completion[source]==0 for source in rule['source_ids'])
                     for key,rule in params['strict']['fatal_errors'].items()}
    if any(fatal_decisions.values()):strict=min(strict,min(
        rule['score'] for key,rule in params['strict']['fatal_errors'].items() if fatal_decisions[key]))
    lenient_decisions={identifier:completion[item['source_id']]==1
                       for identifier,item in params['lenient']['must_have'].items()}
    lenient=float(all(lenient_decisions.values()))
    return {'status':'completed','passed':n['passed'] and s['passed'],'measurement_complete':True,'business_measurement_complete':True,
            'score':strict,'reward':strict,'rewards':{'strict':strict,'lenient':lenient},
            'numeric_score':n['score'],'semantic_score':s['score'],'semantic_fresh_call':s['fresh_call'],
            'rollout_executed':False,'scoring_ledger':{'profile':'bench','settlement':'local_chains',
                'raw_owner_credit':raw_credit,'positive_earned':raw_credit,
                'chains':{key:{'operator':chain['operator'],'weight':chain['weight'],
                    'source_ids':chain['source_ids'],'raw_credit':raw_chain_scores[key],'completion':chain_scores[key]}
                    for key,chain in chains.items()},
                'fatal_errors':fatal_decisions,
                'positive_items':{key:{'completion':value} for key,value in completion.items()},
                'lenient_evaluation':{'must_have':lenient_decisions,
                    'failed_ids':[key for key,value in lenient_decisions.items() if not value]}},
            'score_version':params['version']}

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
                'scope':'The published file contract failed. Business checks and semantic review were not run.','rollout_executed':False}
    params=scoring_params()
    public_input=Path(input_path)
    if CONFIG['input_file']:
        numeric_input=public_input if public_input.is_file() else public_input/CONFIG['input_file']
        semantic_input=numeric_input.parent
    else:numeric_input=public_input;semantic_input=public_input
    if not numeric_input.exists() or not semantic_input.is_dir():raise MeasurementUnavailable('Author-supplied input materials unavailable')
    command=[sys.executable,'-B',str(HERE/'verify.py'),'--submission-dir',str(wb),'--input',str(numeric_input),'--report',str(out/'numeric.json')]
    code=run_command(command,out/'numeric-runtime.txt',timeout)
    if code not in (0,1):raise MeasurementUnavailable('Numeric verifier failed to execute normally')
    numeric=read_receipt(out/'numeric.json')
    normalized_numeric(numeric)
    judge=HERE/'mix_judge/judge.py'
    if not judge.is_file():raise MeasurementUnavailable('Required semantic judge runtime is unavailable')
    command=[sys.executable,'-B',str(judge),'--registers',str(wb),'--report',str(report),'--input',str(semantic_input),'--out',str(out/'semantic')]
    if semantic_replay:command.extend(['--replay',str(semantic_replay)])
    code=run_command(command,out/'semantic-runtime.txt',timeout)
    if code!=0:raise MeasurementUnavailable('Semantic runtime or request-bound replay failed')
    semantic=read_receipt(out/'semantic/review.json')
    result=combine(numeric,semantic,params)
    result['scope']='Published submission contract, independent complete-register checks and content-only semantic review. No visual score or container qualification implied.'
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
                'numeric_score':None,'semantic_score':None,'measurement_error':type(exc).__name__+': '+str(exc),'rollout_executed':False}
        if writable and (a.out/'numeric.json').is_file():
            try:result['numeric_score']=normalized_numeric(read_receipt(a.out/'numeric.json'))['score']
            except Exception:pass
    if writable:(a.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 0 if result['passed'] else (2 if result['status']=='unmeasured' else 1)

if __name__=='__main__':raise SystemExit(main())
