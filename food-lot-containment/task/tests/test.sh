#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "$#" -eq 0 ]; then
  export LLM_JUDGE_MODE="${LLM_JUDGE_MODE:-fresh}"
  export LLM_JUDGE_CACHE_DIR="${LLM_JUDGE_CACHE_DIR:-$PWD/tests/mix_judge/cache}"
  set +e
  python tests/evaluate.py --submission-dir /workspace/output --out /logs/verifier/food-lot-containment-evaluation
  status=$?
  set -e
  if [ "$status" -gt 1 ]; then
    rm -f /logs/verifier/reward.json /logs/verifier/reward.txt \
      /logs/verifier/reward_strict.txt /logs/verifier/reward_lenient.txt
    exit "$status"
  fi
  python tests/write_reward.py /logs/verifier/food-lot-containment-evaluation/result.json /logs/verifier
  exit "$status"
fi
exec python tests/evaluate.py "$@"
