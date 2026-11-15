#!/bin/sh
set -eu
OUT=/logs/verifier
mkdir -p "$OUT"
# Initialise all score files even when the agent produced no artifact.
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"

ANSWER=${1:-/workspace/faers_adjudication.json}
if [ ! -f "$ANSWER" ] && [ -f "${ANSWER%/*}/faers_adjudication.json" ]; then
  ANSWER="${ANSWER%/*}/faers_adjudication.json"
fi
if [ ! -f "$ANSWER" ]; then
  printf '{"reward":0,"rewards":{"strict":0,"lenient":0},"reward_formulas":{"strict":"0","lenient":"0"}}\n' > "$OUT/reward_detail.json"
  exit 0
fi

python3 /tests/validator.py "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || exit 0
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys
detail = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
strict = float(detail.get("rewards", {}).get("strict", detail.get("reward", 0)))
lenient = float(detail.get("rewards", {}).get("lenient", 0))
open(out + "/reward_strict.txt", "w").write(f"{strict:.6f}\n")
open(out + "/reward_lenient.txt", "w").write(f"{lenient:.6f}\n")
open(out + "/reward.txt", "w").write(f"{strict:.6f}\n")
json.dump({"reward": strict, "reward_strict": strict, "reward_lenient": lenient}, open(out + "/reward.json", "w"))
PY
mkdir -p /logs/artifacts
cp "$ANSWER" /logs/artifacts/faers_adjudication.json 2>/dev/null || true
exit 0
