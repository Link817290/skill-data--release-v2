"""Platform wrapper; the canonical contract and Program Judge own all scores."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def lenient_pass(result, policy):
    """Return whether the report clears the source-grounded usable-report floor."""
    completion = {
        item.get('id'): float(item.get('fraction', 0.0))
        for item in result.get('items', [])
        if isinstance(item, dict)
    }
    triggered = {
        item.get('id')
        for item in result.get('deduction_items', [])
        if isinstance(item, dict) and item.get('state') == 'triggered'
    }
    return all(
        completion.get(item_id, 0.0) >= float(minimum)
        for item_id, minimum in policy['positive_minimums'].items()
    ) and not triggered.intersection(policy['forbidden_deductions'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('submission',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    here=Path(__file__).resolve().parent
    contract=next((p/'rubric-contract.json' for p in (here,*here.parents) if (p/'rubric-contract.json').is_file()),None)
    if contract is None: raise RuntimeError('Missing canonical rubric-contract.json')
    artifact = next(
        (
            candidate
            for candidate in (
                args.submission / 'output',
                args.submission / 'artifacts' / 'output',
                args.submission / 'artifacts',
                args.submission,
            )
            if candidate.exists()
        ),
        args.submission,
    )
    # Native PDF libraries may write diagnostics to stdout; use a separate JSON carrier.
    with tempfile.TemporaryDirectory(prefix='insurance-judge-') as folder:
        output=Path(folder)/'program.json'
        process=subprocess.run([sys.executable,'-B','-X','utf8',str(here/'program_judge/task_judge.py'),str(artifact),'--contract',str(contract),'--json',str(output)],capture_output=True,text=True,encoding='utf-8')
        if process.returncode:
            sys.stderr.write(process.stderr)
            return process.returncode
        result=json.loads(output.read_text(encoding='utf-8'))
    policy = json.loads((here / 'lenient-contract.json').read_text(encoding='utf-8'))
    lenient = 1.0 if lenient_pass(result, policy) else 0.0
    result.update(reward=result['final_score'],reward_strict=result['final_score'],reward_lenient=lenient)
    encoded=json.dumps(result,ensure_ascii=False)
    if args.output:
        args.output.write_text(encoded+'\n',encoding='utf-8')
    else:
        print(encoded)
    return 0

if __name__=='__main__': raise SystemExit(main())
