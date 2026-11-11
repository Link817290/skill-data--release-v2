#!/usr/bin/env bash
set -uo pipefail

SUBMISSION="${1:-/workspace}"
OUT="${VERIFIER_OUT:-/logs/verifier}"
mkdir -p "$OUT"
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"

VALIDATOR_PATH="${VALIDATOR_PATH:-/tests/validator.py}"
python3 "$VALIDATOR_PATH" "$SUBMISSION" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys
try:
    detail = json.load(open(sys.argv[1], encoding="utf-8"))
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"]["lenient"])
except Exception as exc:
    sys.stderr.write(f"could not read reward: {exc}\n")
    raise SystemExit(0)
out = sys.argv[2]
for name, value in (("reward_strict.txt", strict), ("reward_lenient.txt", lenient), ("reward.txt", strict)):
    open(out + "/" + name, "w", encoding="utf-8").write(f"{value:.6f}\n")
payload = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
for key, value in (detail.get("dimension_scores") or {}).items():
    payload[key] = float(value)
json.dump(payload, open(out + "/reward.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY

ARTIFACT_SOURCE="$SUBMISSION/output/electrical_drawings.dxf"
if [ ! -f "$ARTIFACT_SOURCE" ] && [ -f "$SUBMISSION/electrical_drawings.dxf" ]; then
    ARTIFACT_SOURCE="$SUBMISSION/electrical_drawings.dxf"
fi
ARTIFACT_OUT="${ARTIFACT_OUT_OVERRIDE:-/logs/artifacts}"
mkdir -p "$ARTIFACT_OUT"
if [ -f "$ARTIFACT_SOURCE" ]; then cp "$ARTIFACT_SOURCE" "$ARTIFACT_OUT/electrical_drawings.dxf"; fi
exit 0
