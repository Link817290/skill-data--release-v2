from pathlib import Path
import argparse,json,subprocess,sys,math
HERE=Path(__file__).resolve().parent;TASK=HERE.parent;PACKAGE=TASK.parent
def run(command,log):
    r=subprocess.run(command,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=900)
    log.write_text(r.stdout+'\n'+r.stderr,encoding='utf8');return r.returncode
def main():
    p=argparse.ArgumentParser();p.add_argument('--submission-dir',type=Path,default=Path('/workspace/output'));p.add_argument('--input',type=Path,default=TASK/'environment/workspace/input');p.add_argument('--out',type=Path,required=True);p.add_argument('--semantic-replay',type=Path);a=p.parse_args()
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
            result.update(status='submission_invalid',measurement_complete=True,score=0,strict_score=0,reward=0,reward_strict=0,reward_lenient=0,rewards={'strict':0,'lenient':0},lenient_score=0,missing=missing)
        else:
            cmd=[sys.executable,'-B',str(HERE/'verify.py'),'--submission-dir',str(submission),'--input',str(a.input),'--out',str(out/'numeric.json')]
            code=run(cmd,out/'numeric-runtime.txt')
            if code not in (0,1):raise RuntimeError('Numeric execution failed')
            numeric=json.loads((out/'numeric.json').read_text(encoding='utf8'))
            if numeric.get('measurement_complete') is not True:raise RuntimeError('Numeric measurement unavailable')
            if numeric.get('artifact_error'):
                result.update(status='submission_invalid',measurement_complete=True,score=0,strict_score=0,reward=0,reward_strict=0,reward_lenient=0,rewards={'strict':0,'lenient':0},lenient_score=0,artifact_error=numeric['artifact_error'])
                (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result));return 1
            cmd=[sys.executable,'-B',str(HERE/'mix_judge/judge.py'),'--submission-dir',str(submission),'--input',str(a.input),'--out',str(out/'semantic')]
            if a.semantic_replay:cmd+=['--replay',str(a.semantic_replay)]
            if run(cmd,out/'semantic-runtime.txt')!=0:raise RuntimeError('Semantic measurement or bound replay unavailable')
            semantic=json.loads((out/'semantic/review.json').read_text(encoding='utf8'))
            if semantic.get('measurement_status')!='completed' or semantic.get('reference_conflict') is not False:raise RuntimeError('Semantic evidence conflict')
            rubric=json.loads((TASK/'rubric.json').read_text(encoding='utf8'))
            settlement=rubric['strict_settlement']
            semantic_atoms={row['id']:float(row['score']) for row in semantic['criteria']}
            numeric_atoms={row['id']:float(row.get('score',row.get('passed'))) for row in numeric['checks']}
            owners={'numeric':float(numeric['score']),'semantic':float(semantic['semantic_score'])}
            weights={key:float(value) for key,value in settlement['weights'].items()}
            if set(weights)!=set(owners) or abs(sum(weights.values())-1)>1e-8:raise ValueError('Invalid strict weights')
            base=sum(weights[key]*owners[key] for key in weights)
            damage_fired=semantic_atoms['d_false_release_damage']==0
            retention=(settlement['damage']['d_false_release_damage']['coefficient'] if damage_fired else 1.0)
            strict=base*retention
            lenient_checks={
                'job_coverage': numeric_atoms['job_coverage']==1,
                'B_pressure': numeric_atoms['B_pressure']==1,
                'host_power_head_state': semantic_atoms['host_power_head_state']==1,
                'consecutive_five_restart': semantic_atoms['consecutive_five_restart']==1,
                'd_capability_hold': semantic_atoms['d_capability_hold']==1,
                'planned_trial_truth': semantic_atoms['planned_trial_truth']==1,
                'chinese_operating_content': semantic_atoms['chinese_operating_content']==1,
            }
            lenient=int(all(lenient_checks.values()))
            for value in [numeric['score'],semantic['semantic_score'],strict]:
                if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid score')
            result.update(status='completed',measurement_complete=True,business_measurement_complete=True,
                passed=numeric['passed'] and semantic['passed'],score=round(strict,12),
                strict_score=round(strict,12),reward=round(strict,12),
                reward_strict=round(strict,12),reward_lenient=lenient,
                rewards={'strict':round(strict,12),'lenient':lenient},
                lenient_score=lenient,lenient_checks=lenient_checks,
                numeric_score=numeric['score'],semantic_score=semantic['semantic_score'],
                semantic_fresh_call=semantic['fresh_call'],positive_earned=base,
                raw_score=base,settlement_family=settlement['family'],global_power=None,compression_ratio=(base/strict if strict>0 else (1.0 if base==0 else None)),owner_completion=owners,strict_weights=weights,
                retention=retention,damage_instances=(
                    [{'id':'D_FALSE_D_RELEASE','item_ids':['d_false_release_damage']}] if damage_fired else []))
    except Exception as e:result['measurement_error']=type(e).__name__+': '+str(e)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
    return 0 if result['passed'] else (2 if result['status']=='unmeasured' else 1)
if __name__=='__main__':raise SystemExit(main())
