"""Grade submitted native Office deliverables; failures are errors, never fake business zeros."""
import argparse
import json
import os
from pathlib import Path
import sys

from judge import measure, read, save
from native_carriers import role, read_office, visible_rows
from settlement import settle
from judge_layout import standardize
import focused_review
import operability_review

HERE = Path(__file__).resolve().parent

def evaluate(artifact, output, mode, cache_dir, focused_mode=None):
    if not artifact.is_dir():
        raise ValueError('Artifact directory does not exist')
    native = [path for path in artifact.iterdir() if path.is_file() and role(path)]
    if {role(path) for path in native} != {'report', 'audit', 'actions'}:
        return {'reward_strict': 0., 'reward_lenient': 0, 'reason': 'Missing a required native report/audit/actions carrier', 'measurements': None}
    rows = [row for path in native for row in visible_rows(read_office(path))]
    if not any(row['text'].strip(' |\t\n') for row in rows):
        return {'reward_strict': 0., 'reward_lenient': 0, 'reason': 'Empty native deliverables', 'measurements': None}
    measured = measure(artifact, output, mode, cache_dir)
    measured = focused_review.apply(artifact, output, focused_mode or mode, cache_dir, measured)
    measured = operability_review.apply(artifact, output, focused_mode or mode, cache_dir, measured)
    standardize(output, cache_dir)
    detail = settle(measured, read(HERE / 'scoring_params.json'))
    detail['measurements'] = measured
    detail['focused_source_reviews'] = read(output / 'judge-result.json')['focused_reviews']
    return detail


def write_rewards(detail, output):
    for name, value in [('reward.txt', detail['reward_strict']), ('reward_strict.txt', detail['reward_strict']), ('reward_lenient.txt', detail['reward_lenient'])]:
        (output / name).write_text(str(value) + '\n')
    save(output / 'reward.json', {'reward': detail['reward_strict'], 'reward_strict': detail['reward_strict'], 'reward_lenient': detail['reward_lenient']})
    save(output / 'reward_detail.json', detail)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', type=Path, default=Path(os.environ.get('OUTPUT_DIR', '/workspace/output')))
    parser.add_argument('--output', type=Path, default=Path(os.environ.get('REWARD_DIR', '/logs/verifier')))
    parser.add_argument('--mode', choices=('replay', 'fresh'), default='replay')
    parser.add_argument('--cache-dir', type=Path, default=Path('/tmp/female-judge-cache'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ('reward.txt', 'reward_strict.txt', 'reward_lenient.txt', 'reward.json', 'reward_detail.json', 'scoring-error.json', 'judge-result.json', 'llm_judge_result.json'):
        (args.output / name).unlink(missing_ok=True)
    try:
        detail = evaluate(args.artifact, args.output, args.mode, args.cache_dir)
        write_rewards(detail, args.output)
        print(json.dumps({'reward_strict': detail['reward_strict'], 'reward_lenient': detail['reward_lenient']}))
        return 0
    except Exception as error:
        message = str(error)
        secret = os.environ.get('LLM_JUDGE_API_KEY', '')
        if secret:
            message = message.replace(secret, '[redacted]')
        save(args.output / 'scoring-error.json', {'status': 'scoring_error', 'type': type(error).__name__, 'message': message})
        print('Scoring error: ' + message, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
