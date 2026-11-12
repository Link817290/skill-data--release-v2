#!/usr/bin/env bash
set -uo pipefail

SUBMISSION="${1:-/workspace}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
# Leave a parseable zero behind even if the verifier cannot start or emit JSON.
printf '0.0000\n' >"$OUT/reward.txt"
printf '0.0000\n' >"$OUT/reward_strict.txt"
printf '0.0000\n' >"$OUT/reward_lenient.txt"
printf '{"reward":0.0,"reward_strict":0.0,"reward_lenient":0.0}\n' >"$OUT/reward.json"
python3 "$(dirname "$0")/validator.py" "$SUBMISSION" >"$OUT/reward_detail.json" 2>"$OUT/validator.log"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward.json"
  printf '{"status":"unmeasured","measurement_complete":false,"error":"validator or semantic judge failed"}\n' > "$OUT/verifier_status.json"
  exit 2
fi

python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json
import sys

detail_path, out = sys.argv[1:]
try:
    detail = json.load(open(detail_path, encoding="utf-8"))
    rewards = detail.get("rewards", {})
    strict = float(rewards["strict"])
    lenient = float(rewards["lenient"])
except Exception:
    strict = 0.0
    lenient = 0.0
for name, value in (("reward.txt", strict), ("reward_strict.txt", strict),
                    ("reward_lenient.txt", lenient)):
    with open(f"{out}/{name}", "w", encoding="utf-8") as fh:
        fh.write(f"{value:.4f}\n")
with open(f"{out}/reward.json", "w", encoding="utf-8") as fh:
    json.dump({"reward": strict, "reward_strict": strict, "reward_lenient": lenient}, fh)
PY
