#!/bin/sh
set -eu
if [ "$#" -eq 0 ]; then
  cd "$(dirname "$0")/.."
  export LLM_JUDGE_MODE="${LLM_JUDGE_MODE:-replay}"
  export LLM_JUDGE_CACHE_DIR="${LLM_JUDGE_CACHE_DIR:-$PWD/tests/mix_judge/cache}"
  set +e
  python -B tests/evaluate.py --submission-dir "${SUBMISSION_DIR:-/workspace/output}" --out "${VERIFIER_OUT:-/logs/verifier/delivery-evaluation}"
  status=$?
  set -e
  if [ "$status" -gt 1 ]; then
    rm -f /logs/verifier/reward.json /logs/verifier/reward.txt \
      /logs/verifier/reward_strict.txt /logs/verifier/reward_lenient.txt
    exit "$status"
  fi
  python -B tests/write_reward.py "${VERIFIER_OUT:-/logs/verifier/delivery-evaluation}/result.json" /logs/verifier
  exit "$status"
fi
if [ "$#" -ne 2 ]; then
  echo "Usage: test.sh [COMPLETED_WORKBOOK_XLSX EXTERNAL_REPORT_JSON]" >&2
  exit 2
fi
cd "$(dirname "$0")/.."
python tests/workbook_verify.py --workbook "$1" --report "$2"
