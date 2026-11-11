"""Public strict workbook verifier. Infrastructure failures never become zero."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from quality_scoring import completion,settle
from lenient_scoring import evaluate as evaluate_lenient

HERE=Path(__file__).resolve().parent
MATERIAL = HERE.parent / 'environment' / 'materials' / 'workspace.xlsx'
if not MATERIAL.is_file():
    MATERIAL = HERE / 'material.xlsx'


def run(command,output):
    start=datetime.now(timezone.utc).isoformat()
    done=subprocess.run(command,capture_output=True,text=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'command':command,'started_at':start,'finished_at':datetime.now(timezone.utc).isoformat(),
        'exit_code':done.returncode,'stdout':done.stdout,'stderr':done.stderr},indent=2)+'\n')
    if done.returncode:raise RuntimeError('Verifier dependency failed; see '+str(output))


def write_rewards(output,result):
    strict=float(result['rewards']['strict'])
    lenient=float(result['rewards']['lenient'])
    (output/'reward_detail.json').write_text(json.dumps(result,indent=2)+'\n')
    (output/'reward.json').write_text(json.dumps({
        'reward':strict,'reward_strict':strict,'reward_lenient':lenient},indent=2)+'\n')
    (output/'reward.txt').write_text(f'{strict:.12g}\n')
    (output/'reward_strict.txt').write_text(f'{strict:.12g}\n')
    (output/'reward_lenient.txt').write_text(f'{lenient:.12g}\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('--mode',choices=['auto','fresh','replay'],default='auto')
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--cache-dir',default=os.environ.get('LLM_JUDGE_CACHE_DIR','/logs/verifier/judge-cache'))
    parser.add_argument('--golden-replay-dir',default=str(HERE/'llm_judge/golden_replay'))
    parser.add_argument('--measurements')
    args=parser.parse_args()
    supplied=Path(args.root).resolve()
    artifact=supplied if supplied.is_file() else supplied/'output/fixed_asset_model.xlsx'
    if not artifact.is_file() and supplied.is_dir() and (supplied/'fixed_asset_model.xlsx').is_file():
        artifact=supplied/'fixed_asset_model.xlsx'
    output=Path(args.output or os.environ.get('VERIFIER_OUTPUT_DIR') or tempfile.mkdtemp(prefix='mx6-verifier-')).resolve()
    output.mkdir(parents=True,exist_ok=True)
    if not artifact.is_file():
        result={'rewards':{'strict':0.0,'lenient':0},'status':'business_missing_required_workbook',
                'must_have':{'native_integrity':{'passed':0,'reason':'Required workbook is absent.'}}}
    else:
        native=Path(args.measurements).resolve() if args.measurements else output/'native'
        if not args.measurements:
            run([sys.executable,'-B',str(HERE/'runtime/measure.py'),'--artifact',str(artifact),'--material',str(MATERIAL),
                 '--output',str(native)],output/'logs/native.json')
        judge_command=[sys.executable,'-B',str(HERE/'llm_judge/judge.py'),'--mode',args.mode,'--artifact',str(artifact),
            '--output',str(output/'semantic'),'--cache-dir',str(Path(args.cache_dir).resolve()),'--material',str(MATERIAL),
            '--golden-replay-dir',str(Path(args.golden_replay_dir).resolve()),
            '--observations',str(native/'diagnostics/diagnostics.json')]
        if args.refresh:judge_command.append('--refresh')
        run(judge_command,output/'logs/semantic.json')
        measured=completion(artifact,MATERIAL,native/'valid',native/'diagnostics/diagnostics.json',
            native/'source/source-observation.json',output/'semantic/decision.json',HERE/'runtime/scenarios.json')
        parameters=json.loads((HERE/'scoring_params.json').read_text())
        result=settle(measured,parameters)
        loose=evaluate_lenient(artifact,MATERIAL,native/'valid',native/'source/source-observation.json',output/'semantic/decision.json',measured['completion'])
        result['rewards']['lenient']=loose['reward']
        result['must_have']=loose['must_have']
        result['lenient_evaluation']={'policy':'Independent binary must-have conjunction','failed_ids':loose['failed_ids']}
        result['status']='measured'
    result['reward']=result['rewards']['strict']
    write_rewards(output,result)
    print(json.dumps({'rewards':result['rewards'],'status':result['status']}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'verifier_error','error_type':type(error).__name__,'message':str(error),'candidate_score_assigned':False}),file=sys.stderr)
        raise SystemExit(2)
