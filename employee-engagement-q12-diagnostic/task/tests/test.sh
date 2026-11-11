#!/usr/bin/env bash
set -uo pipefail

SUBMISSION="${1:-/workspace}"
OUT=/logs/verifier
if [ -n "${VERIFIER_OUT:-}" ]; then
  OUT="$VERIFIER_OUT"
fi
mkdir -p "$OUT"
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
printf '0\n' > "$OUT/reward.txt"

VALIDATOR_PATH="${VALIDATOR_PATH:-/tests/validator.py}"
python3 "$VALIDATOR_PATH" "$SUBMISSION" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json
import sys

try:
    detail = json.load(open(sys.argv[1], encoding="utf-8"))
    if detail.get("status") == "unmeasured":
        for name in ("reward.json","reward.txt","reward_strict.txt","reward_lenient.txt"):
            try: __import__('os').unlink(sys.argv[2] + "/" + name)
            except FileNotFoundError: pass
        json.dump(detail, open(sys.argv[2] + "/verifier_status.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
        raise SystemExit(2)
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"]["lenient"])
except Exception as exc:
    sys.stderr.write(f"could not read reward: {exc}\n")
    raise SystemExit(0)

out = sys.argv[2]
open(out + "/reward_strict.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
open(out + "/reward_lenient.txt", "w", encoding="utf-8").write(f"{lenient:.6f}\n")
open(out + "/reward.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
payload = {
    "reward": strict,
    "reward_strict": strict,
    "reward_lenient": lenient,
}
for key, value in (detail.get("dimension_scores") or {}).items():
    payload[key] = float(value)
json.dump(payload, open(out + "/reward.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
SETTLEMENT_STATUS=$?
if [ "$SETTLEMENT_STATUS" -ne 0 ]; then
  exit "$SETTLEMENT_STATUS"
fi

ARTIFACT_SOURCE=/workspace/output
if [ -d "$SUBMISSION/output" ]; then
  ARTIFACT_SOURCE="$SUBMISSION/output"
fi

ARTIFACT_OUT=/logs/artifacts
if [ -n "${ARTIFACT_OUT_OVERRIDE:-}" ]; then
  ARTIFACT_OUT="$ARTIFACT_OUT_OVERRIDE"
fi
mkdir -p "$ARTIFACT_OUT"
for name in cleaned_samples.xlsx engagement_analysis.xlsx; do
  if [ -f "$ARTIFACT_SOURCE/$name" ]; then
    cp "$ARTIFACT_SOURCE/$name" "$ARTIFACT_OUT/$name"
  fi
done
exit 0
