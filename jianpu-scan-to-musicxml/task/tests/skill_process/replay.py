"""Replay the frozen Skill-process judgments without a model or API endpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import official_judge as J

ID = 'jianpu-scan-to-musicxml'
FRAMEWORK_SHA = 'ef656760e10de934f88727adb768cf08978dbb6da65e3e05fc0fb948f95a3634'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def replay(root, row, process):
    frozen_path = process / row['output']
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    hashes = frozen['hashes']
    evidence = process / 'replay_evidence' / hashes['trajectory_sha256']
    proof = json.loads((evidence / 'serialization.json').read_text(encoding='utf-8'))
    check(sha(frozen_path.read_bytes()) == proof['frozen_result_sha256'], 'Frozen result serialization changed')
    task = root / 'tasks' / ID
    trajectory_path = root / row['run'] / 'trajectory.json'
    trajectory_text = J.read_text(trajectory_path)
    check(J.sha256_text(trajectory_text) == hashes['trajectory_sha256'] == row['trajectory_sha256'], 'Trajectory binding differs')
    contract = J.validate_contract(json.loads((process / 'skill_execution_contract.json').read_text(encoding='utf-8')))
    check(J.sha256_text(J.canonical_json(contract)) == hashes['contract_sha256'], 'Contract binding differs')
    instruction = J.read_text(task / 'instruction.md')
    check(J.sha256_text(instruction) == hashes['instruction_sha256'], 'Instruction binding differs')
    skills = [(entry['label'], J.read_text(task / 'environment/skills' / entry['label'])) for entry in hashes['skills']]
    for (label, text), binding in zip(skills, hashes['skills']):
        check(J.sha256_text(text) == binding['sha256'], 'Skill binding differs: ' + label)
    trace, visible = J.compact_trajectory(json.loads(trajectory_text), 120000, 1200)
    check(sorted(visible) == frozen['input_policy']['observable_step_ids'], 'Observable step IDs differ')
    check(J.sha256_text(trace) == hashes['sanitized_trace_sha256'], 'Sanitized trace binding differs')
    check((evidence / 'sanitized_trace.txt').read_bytes() == trace.encode('utf-8'), 'Sanitized trace serialization differs')
    prompt = J.build_prompt(instruction, skills, contract, trace)
    check(J.sha256_text(prompt) == hashes['prompt_sha256'], 'Prompt binding differs')
    check((evidence / 'request.txt').read_bytes() == prompt.encode('utf-8'), 'Evaluator request text differs')
    response_bytes = (evidence / 'accepted_response.json').read_bytes()
    check(sha(response_bytes) == hashes['judge_response_sha256'], 'Accepted response binding differs')
    response = json.loads(response_bytes)
    check(response_bytes == J.canonical_json(response).encode('utf-8'), 'Response is not the original canonical serialization')
    response = J.validate_response(response, contract, visible)
    check(J.sha256_text(J.canonical_json(response)) == hashes['judge_response_sha256'], 'Validated response binding differs')
    raw, score, dimensions = J.calculate_score(response, contract)
    check(raw == frozen['reward_process_raw'], 'Raw process score differs')
    check(score == frozen['reward_process'] == row['reward_process'], 'Process score differs')
    check(dimensions == frozen['dimensions'], 'Frozen dimension decisions differ')
    for name in ('fatal_flags', 'overall_assessment', 'confidence', 'limitations'):
        check(response[name] == frozen[name], 'Frozen decision field differs: ' + name)
    return dict(run=row['run'], status='measured_offline', reward_process_raw=raw, reward_process=score,
                expected_reward_process=frozen['reward_process'], exact_match=True,
                hashes=hashes, source_bindings_verified=True, observable_step_ids_verified=True,
                request_kind='Verified evaluator prompt text; not an HTTP envelope.',
                response_kind='Verified canonical accepted semantic response; not an HTTP envelope.',
                api_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run', help='Optional complete trajectory path from skill_execution_summary.json')
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    check(not output.is_relative_to(root) and not root.is_relative_to(output), 'Output must be outside the read-only delivery root')
    check(sha(Path(J.__file__).read_bytes()) == FRAMEWORK_SHA, 'Original judge framework changed')
    check(not output.exists() or not any(output.iterdir()), 'Output directory must be new or empty')
    process = root / 'docs' / ID / 'skill_execution'
    summary = json.loads((process / 'skill_execution_summary.json').read_text(encoding='utf-8'))
    rows = [row for row in summary['rows'] if args.run is None or row['run'] == args.run]
    check(bool(rows), 'No frozen process case selected')
    results = [replay(root, row, process) for row in rows]
    output.mkdir(parents=True, exist_ok=True)
    for result in results:
        name = result['run'].replace('/', '__') + '.json'
        (output / name).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = dict(status='verified', instance_id=ID, measured_cases=len(results), exact_matches=len(results),
                  framework_sha256=FRAMEWORK_SHA, api_calls=0, results=results,
                  http_transport_recovered=False,
                  limitation='Original HTTP envelopes were not saved by the successful historical judge path; only exact frozen-hash prompt/trace and accepted-response serializations are verified.')
    (output / 'replay-summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status='verified', measured_cases=len(results), exact_matches=len(results), api_calls=0)))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(1)
