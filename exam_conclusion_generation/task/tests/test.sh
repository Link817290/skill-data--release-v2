#!/usr/bin/env bash
set -uo pipefail

TESTS="${TESTS_DIR:-/tests}"
SOLUTION="${SOLUTION_DIR:-/solution}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"

if [ ! -f "$TESTS/validator.py" ]; then
  TESTS="$(cd "$(dirname "$0")" && pwd)"
fi
if [ ! -f "$SOLUTION/solve.sh" ]; then
  SOLUTION="$TESTS/../solution"
fi

WORKSPACE="${AGENT_WORKSPACE:-/app/environment/workspace}"
for candidate in "$WORKSPACE" "$PWD" /app/environment/workspace /app/workspace /workspace /logs/artifacts/workspace; do
  if [ -f "$candidate/匿名体检检查明细.xlsx" ]; then
    WORKSPACE="$candidate"
    break
  fi
done

mkdir -p "$OUT" 2>/dev/null || OUT="${VERIFIER_OUTPUT_DIR:-$PWD/_verifier}"
mkdir -p "$OUT"

# Candidate failures (including a missing deliverable) receive zero. Infrastructure
# failures below remove these provisional files and return a verifier error.
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"

if [ "${RUN_GOLDEN_SOLUTION:-0}" = "1" ] && [ -f "$SOLUTION/solve.sh" ]; then
  AGENT_WORKSPACE="$WORKSPACE" PYTHON_BIN="$PYTHON_BIN" bash "$SOLUTION/solve.sh" > "$OUT/golden.log" 2>&1
fi

# Keep the deliverable with the trajectory so the score can be recomputed later
# without re-running the rollout.
mkdir -p /logs/artifacts
cp "$WORKSPACE/体检总检结论.xlsx" /logs/artifacts/体检总检结论.xlsx 2>/dev/null || true

"$PYTHON_BIN" "$TESTS/validator.py" "$WORKSPACE" "$OUT/reward_detail.json" > "$OUT/validator.log" 2>&1
STATUS=$?
cat "$OUT/validator.log"
if [ "$STATUS" -ne 0 ]; then
  # A required semantic service failure is not a candidate business score.
  # Remove both stale and prewritten scores before returning an evaluator error.
  rm -f "$OUT"/reward*.json "$OUT"/reward*.txt
  printf '%s\n' 'Evaluator could not complete; no score published.' >&2
  exit 2
fi
# Two co-equal standards, one file each. reward.txt mirrors the strict standard
# so a single-scalar consumer (Harbor) keeps reading a number; it is not a third
# score.
"$PYTHON_BIN" - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
OUT = sys.argv[2]
rewards = d.get("rewards") or {}
strict = float(rewards.get("strict", d.get("reward", 0.0)))
lenient = float(rewards.get("lenient", d.get("reward_lenient", 0.0)))
open(OUT + "/reward_strict.txt", "w").write("%.6f\n" % strict)
open(OUT + "/reward_lenient.txt", "w").write("%.6f\n" % lenient)
open(OUT + "/reward.txt", "w").write("%.6f\n" % strict)
json.dump(
    {"reward": strict, "reward_strict": strict, "reward_lenient": lenient},
    open(OUT + "/reward.json", "w"),
    indent=2,
)
print("reward_strict=%.6f reward_lenient=%.6f" % (strict, lenient))
PY
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  rm -f "$OUT"/reward*.json "$OUT"/reward*.txt
  exit 2
fi
exit 0
