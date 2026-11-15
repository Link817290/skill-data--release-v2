"""Public semantic CLI. Numeric reward is exclusively written by the verifier."""
import argparse
import os
from pathlib import Path
import sys

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS))
from judge import measure, save
from judge_layout import standardize
import focused_review
import operability_review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('replay', 'fresh'), required=True)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, default=Path('/tmp/female-judge-cache'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'llm_judge_result.json').unlink(missing_ok=True)
    try:
        if args.mode == 'fresh' and not args.refresh:
            raise ValueError('Fresh mode requires explicit --refresh')
        measured = measure(args.artifact, args.output, args.mode, args.cache_dir)
        measured = focused_review.apply(args.artifact, args.output, args.mode, args.cache_dir, measured)
        operability_review.apply(args.artifact, args.output, args.mode, args.cache_dir, measured)
        standardize(args.output, args.cache_dir)
        print('Semantic measurements validated; numeric reward remains program-owned.')
        return 0
    except Exception as error:
        message = str(error)
        key = os.environ.get('LLM_JUDGE_API_KEY', '')
        if key:
            message = message.replace(key, '[redacted]')
        save(args.output / 'llm_judge_result.json', {'status': 'judge_error', 'error_type': type(error).__name__, 'error': message})
        print('Semantic judgment incomplete: ' + message, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
