#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export LLM_JUDGE_MODE="${LLM_JUDGE_MODE:-replay}"
export LLM_JUDGE_CACHE_DIR="${LLM_JUDGE_CACHE_DIR:-$PWD/tests/mix_judge/cache}"
if [ "$#" -eq 0 ]; then
  exec python3 -B tests/validator.py --submission-dir /workspace/output \
    --out /logs/verifier/shutdown-maintenance-evaluation --publish-dir /logs/verifier
fi
exec python3 -B tests/validator.py "$@"
