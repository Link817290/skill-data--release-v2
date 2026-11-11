#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
set +e
python -B tests/evaluate.py --submission-dir /workspace/output --out /logs/verifier/equipment-changeover-evaluation
code=$?
set -e
if [ "$code" -gt 1 ]; then
  rm -f /logs/verifier/reward.json /logs/verifier/reward.txt \
    /logs/verifier/reward_strict.txt /logs/verifier/reward_lenient.txt
  exit "$code"
fi
python -B tests/write_reward.py
exit $code
