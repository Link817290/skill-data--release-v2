"""Apply the shared published-file gate, then the native business evaluator."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from deliverable_gate import check

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--submission-dir', type=Path, required=True)
    parser.add_argument('--input', type=Path, default=HERE.parent / 'environment/workspace/input')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--semantic-replay', type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    policy = json.loads((HERE.parent / 'rubric.json').read_text())['delivery_gate']
    reports = [name for name in policy['report_alternatives']
               if (args.submission_dir / name).is_file()]
    report = reports[0] if reports else policy['report_alternatives'][0]
    config = {key: policy[key] for key in ['root','allowlist','extra_coefficient','extra_cap','item_id']}
    config['required'] = policy['required'] + [report]
    gate = check(args.submission_dir, config)
    if gate['missing']:
        result = {'status': 'submission_invalid', 'measurement_complete': True, 'passed': False,
                  'score': 0.0, 'numeric_score': None, 'semantic_score': None,
                  'lenient_score': 0, 'rewards': {'strict': 0.0, 'lenient': 0},
                  'lenient_evaluation': {'must_have': {'published_delivery': {'passed': False,
                      'evidence': {'missing': gate['missing']}}}, 'failed_ids': ['published_delivery']},
                  'deliverable_gate': gate, 'business_measurement_complete': False,
                  'reason': 'A required published deliverable is absent; shared Bench delivery gate assigns genuine failure, not an infrastructure zero.'}
    else:
        command = [sys.executable, '-B', str(HERE / 'evaluate_business.py'),
                   '--workbook', str(args.submission_dir / 'analysis.xlsx'),
                   '--decision-report', str(args.submission_dir / report), '--input', str(args.input),
                   '--out', str(args.out / 'business')]
        if args.semantic_replay:
            command += ['--semantic-replay', str(args.semantic_replay)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=1100)
        (args.out / 'business-runtime.txt').write_text(process.stdout + '\n' + process.stderr)
        path = args.out / 'business/result.json'
        result = json.loads(path.read_text()) if path.exists() else {
            'status': 'unmeasured', 'measurement_complete': False, 'score': None}
        if result.get('measurement_complete'):
            strict = json.loads((HERE.parent / 'rubric.json').read_text())['strict_scoring']
            damage_policy = strict['delivery_damage']
            charged = gate['extra'][:damage_policy['maximum_instances']]
            utility = result['score']
            damage_instances = [
                {'key': 'deliverable:extra:' + name, 'item_ids': [damage_policy['item_id']],
                 'penalty': damage_policy['penalty']}
                for name in charged
            ]
            for key, active in result.get('critical_errors', {}).items():
                if active:
                    policy = strict['critical_error_damage'][key]
                    damage_instances.append({'key': 'critical:' + key,
                        'item_ids': [policy['item_id']], 'penalty': policy['penalty']})
            damage = sum(item['penalty'] for item in damage_instances)
            final = max(strict['minimum_retention'] * utility, utility - damage)
            ledger = {
                'positive_earned': result['raw_quality'],
                'aggregation': strict['aggregation'],
                'positive_utility': utility,
                'damage': damage,
                'minimum_retention': strict['minimum_retention'],
                'final_score': round(final, 12),
                'damage_instances': damage_instances,
                'deliverable_gate': {
                    'schema_version': 'deliverable-gate-v1', 'missing': gate['missing'],
                    'extra': gate['extra'], 'charged': charged,
                    'penalty': damage_policy['penalty'], 'cap': damage_policy['maximum_instances'],
                    'item_id': damage_policy['item_id']}
            }
            result.update(status='completed', score=ledger['final_score'], scoring_ledger=ledger,
                          passed=bool(result['passed'] and not gate['extra']), deliverable_gate=gate)
            must_have={'published_delivery': {'passed': True, 'evidence': {'missing': [], 'selected_report': report}},
                       **result['must_have']}
            failed=[key for key,value in must_have.items() if value['passed'] is not True]
            result.update(lenient_score=int(not failed),rewards={'strict':ledger['final_score'],'lenient':int(not failed)},
                          lenient_evaluation={'must_have':must_have,'failed_ids':failed})
        else:
            result['deliverable_gate'] = gate
    (args.out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('passed') else (1 if result.get('measurement_complete') else 2)


if __name__ == '__main__':
    raise SystemExit(main())
