from pathlib import Path
import argparse,json,subprocess,sys,math,os
HERE=Path(__file__).resolve().parent;TASK=HERE.parent;PACKAGE=TASK.parent
def run(command,log,env=None):
    r=subprocess.run(command,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=900,env=env)
    log.write_text(r.stdout+'\n'+r.stderr,encoding='utf8');return r.returncode
def measured_atoms(numeric,semantic,params):
    strict=params['strict']
    expected_numeric=(set(strict['schedule_witness']['numeric'])
                      |set(strict['independent_controls']['numeric'])
                      |set(strict['completion_reference']['numeric']))
    observed_numeric={row['id']:float(row.get('score',row.get('passed'))) for row in numeric.get('checks',[])}
    effective_zero=(numeric.get('measurement_complete') is True and numeric.get('score')==0
                    and set(observed_numeric)!=expected_numeric and all(value==0 for value in observed_numeric.values()))
    if effective_zero:observed_numeric={key:0. for key in expected_numeric}
    if set(observed_numeric)!=expected_numeric:raise RuntimeError('Numeric atom coverage incomplete')
    observed_semantic={row['id']:float(row['score']) for row in semantic['criteria']}
    expected_semantic=(set(strict['schedule_witness']['semantic'])
                       |set(strict['independent_controls']['semantic'])
                       |set(strict['completion_reference']['semantic']))
    if set(observed_semantic)!=expected_semantic:raise RuntimeError('Semantic atom coverage incomplete')
    return observed_numeric,observed_semantic,effective_zero
def settle(numeric,semantic,maintainability,params):
    n,s,effective_zero=measured_atoms(numeric,semantic,params)
    config=params['strict']
    witness=config['schedule_witness']
    if witness['operator']!='mean':raise ValueError('Unsupported schedule witness operator')
    witness_values=[n[key] for key in witness['numeric']]+[s[key] for key in witness['semantic']]
    schedule_witness=sum(witness_values)/len(witness_values)
    controls=config['independent_controls']
    if controls['operator']!='weighted_mean':raise ValueError('Unsupported control operator')
    control_weight=sum(controls['numeric'].values())+sum(controls['semantic'].values())
    if not math.isclose(control_weight,.336,abs_tol=1e-12):raise ValueError('Unexpected control weight total')
    control_total=sum(controls['numeric'][key]*n[key] for key in controls['numeric'])
    control_total+=sum(controls['semantic'][key]*s[key] for key in controls['semantic'])
    independent_controls=control_total/control_weight
    reference=config['completion_reference']
    business_strict=sum(reference['numeric'][key]*n[key] for key in reference['numeric'])
    business_strict+=sum(reference['semantic'][key]*s[key] for key in reference['semantic'])
    maintain={row['id']:float(row['score']) for row in maintainability['criteria']}
    if set(maintain)!={'embedded_independent_validation_receipt','maintainable_event_update_mechanism'}:
        raise RuntimeError('Maintainability atom coverage incomplete')
    maintainability_score=(maintain['embedded_independent_validation_receipt']
                           +maintain['maintainable_event_update_mechanism'])/2
    strict=.90*business_strict+.10*maintainability_score
    completion_reference=business_strict
    must={
      'core_schedule':all(n[key]==1 for key in ['scope','duration_windows','resource_feasibility','coupled_precedence']),
      'calendar_matches_schedule':n['gantt_consistency']==1,
      'planning_basis':s['estimated_duration_basis']==1,
      'safe_handback':s['candidate_handback_and_electrical_boundary']==1,
      'standby_handoff':s['continuous_standby_and_response']==1,
    }
    return strict,must,dict(
        numeric=n,semantic=s,effective_numeric_gate_zero=effective_zero,
        schedule_witness=schedule_witness,independent_controls=independent_controls,
        completion_reference=completion_reference,
        business_strict=business_strict,maintainability=maintain,
        maintainability_score=maintainability_score,
        compression_ratio=(completion_reference/strict if strict else None),
        fatal_error=False,
    )
def main():
    p=argparse.ArgumentParser();p.add_argument('--submission-dir',type=Path,default=Path('/workspace/output'));p.add_argument('--input',type=Path,default=TASK/'environment/workspace/input');p.add_argument('--out',type=Path,required=True);p.add_argument('--semantic-replay',type=Path);p.add_argument('--maintainability-replay',type=Path);a=p.parse_args()
    out=a.out.resolve();submission=a.submission_dir.resolve()
    if out==PACKAGE or PACKAGE in out.parents or out==submission or submission in out.parents:raise SystemExit('Use an external result directory.')
    if out.exists() and any(out.iterdir()):raise SystemExit('Use a new result directory.')
    out.mkdir(parents=True,exist_ok=True)
    result={'status':'unmeasured','passed':False,'measurement_complete':False,'score':None,'rollout_executed':False}
    try:
        if not a.input.is_dir() or not any(a.input.rglob('*.docx')):raise RuntimeError('Public business input unavailable')
        contract=json.loads((HERE/'mix_judge/contract.json').read_text(encoding='utf8'))
        if any(not (a.input/name).is_file() for name in contract['required_inputs']):raise RuntimeError('Required public inputs unavailable')
        json.loads((HERE/'reference/facts.json').read_text(encoding='utf8'))
        missing=[name for name in contract['outputs'] if not (submission/name).is_file() or not (submission/name).stat().st_size]
        if missing:
            result.update(status='submission_invalid',measurement_complete=True,score=0,
                rewards={'strict':0.0,'lenient':0.0},
                lenient_evaluation={'must_have':{},'failed_ids':['published_output'],'score':0.0},
                missing=missing)
        else:
            cmd=[sys.executable,'-B',str(HERE/'verify.py'),'--submission-dir',str(submission),'--input',str(a.input),'--out',str(out/'numeric.json')]
            code=run(cmd,out/'numeric-runtime.txt')
            if code not in (0,1):raise RuntimeError('Numeric execution failed')
            numeric=json.loads((out/'numeric.json').read_text(encoding='utf8'))
            if numeric.get('measurement_complete') is not True:raise RuntimeError('Numeric measurement unavailable')
            if numeric.get('artifact_error'):
                result.update(status='submission_invalid',measurement_complete=True,score=0,
                    rewards={'strict':0.0,'lenient':0.0},
                    lenient_evaluation={'must_have':{},'failed_ids':['parseable_workbook'],'score':0.0},
                    artifact_error=numeric['artifact_error'])
                (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result));return 1
            cmd=[sys.executable,'-B',str(HERE/'mix_judge/judge.py'),'--submission-dir',str(submission),'--input',str(a.input),'--out',str(out/'semantic')]
            if a.semantic_replay:cmd+=['--replay',str(a.semantic_replay)]
            if run(cmd,out/'semantic-runtime.txt')!=0:raise RuntimeError('Semantic measurement or bound replay unavailable')
            semantic=json.loads((out/'semantic/review.json').read_text(encoding='utf8'))
            if semantic.get('measurement_status')!='completed' or semantic.get('reference_conflict') is not False:raise RuntimeError('Semantic evidence conflict')
            cmd=[sys.executable,'-B',str(HERE/'maintainability_judge/judge.py'),'--submission-dir',str(submission),'--input',str(a.input),'--out',str(out/'maintainability')]
            if a.maintainability_replay:cmd+=['--replay',str(a.maintainability_replay)]
            maintain_env=dict(os.environ,LLM_JUDGE_CACHE_DIR=str(HERE/'maintainability_judge/cache'))
            if run(cmd,out/'maintainability-runtime.txt',env=maintain_env)!=0:raise RuntimeError('Maintainability measurement or bound replay unavailable')
            maintainability=json.loads((out/'maintainability/review.json').read_text(encoding='utf8'))
            if maintainability.get('measurement_status')!='completed' or maintainability.get('reference_conflict') is not False:raise RuntimeError('Maintainability evidence conflict')
            params=json.loads((HERE/'scoring_params.json').read_text(encoding='utf8'))
            for value in [numeric['score'],semantic['semantic_score'],maintainability['semantic_score']]:
                if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid score')
            strict,must,ledger=settle(numeric,semantic,maintainability,params)
            lenient=float(all(must.values()))
            result.update(status='completed',measurement_complete=True,business_measurement_complete=True,
                passed=numeric['passed'] and semantic['passed'] and maintainability['passed'],score=round(strict,12),
                rewards={'strict':round(strict,12),'lenient':lenient},
                numeric_score=numeric['score'],semantic_score=semantic['semantic_score'],
                maintainability_score=maintainability['semantic_score'],
                semantic_fresh_call=semantic['fresh_call'],maintainability_fresh_call=maintainability['fresh_call'],
                strict_ledger={**ledger,'formula':params['strict']['formula'],
                    'settlement':params['strict']['settlement']},
                lenient_evaluation={'must_have':must,'failed_ids':[key for key,value in must.items() if not value],
                                    'score':lenient})
    except Exception as e:result['measurement_error']=type(e).__name__+': '+str(e)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
    return 0 if result['passed'] else (2 if result['status']=='unmeasured' else 1)
if __name__=='__main__':raise SystemExit(main())
