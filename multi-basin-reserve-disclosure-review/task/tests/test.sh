#!/bin/bash
set -uo pipefail
# A required judge/service/schema failure is an infrastructure error, never a candidate zero.
set -eE
abort_scoring() {
  local target="${OUT:-}"
  if [ -n "$target" ]; then
    rm -f "$target"/reward.txt "$target"/reward_strict.txt "$target"/reward_lenient.txt \
      "$target"/reward.json "$target"/reward_detail.json "$target"/verify_result.json \
      "$target"/program_reward_detail.json
  fi
  exit 2
}
trap abort_scoring ERR
ANSWER="${1:-/workspace/output/reserve_disclosure_review.md}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"

# Initialize every score unconditionally so a missing artifact remains a scored failure.
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"

python3 "$(dirname "$0")/validator.py" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || abort_scoring
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json
import sys

try:
    detail = json.load(open(sys.argv[1], encoding="utf-8"))
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"]["lenient"])
except Exception as exc:
    sys.stderr.write(f"could not read validator result: {exc}\n")
    raise SystemExit(2)

out = sys.argv[2]
open(out + "/reward_strict.txt", "w").write(f"{strict:.6f}\n")
open(out + "/reward_lenient.txt", "w").write(f"{lenient:.6f}\n")
open(out + "/reward.txt", "w").write(f"{strict:.6f}\n")
payload = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
for key, value in (detail.get("group_points") or {}).items():
    payload[key] = float(value)
json.dump(payload, open(out + "/reward.json", "w"), indent=2)
PY

MEMO="$ANSWER"
if [ -d "$ANSWER" ]; then
  MEMO="$ANSWER/reserve_disclosure_review.md"
fi
REGISTER="$(dirname "$MEMO")/reserve_disclosure_register.csv"
mkdir -p /logs/artifacts
cp "$MEMO" "$OUT/reserve_disclosure_review.md" 2>/dev/null || true
cp "$REGISTER" "$OUT/reserve_disclosure_register.csv" 2>/dev/null || true
cp "$MEMO" /logs/artifacts/reserve_disclosure_review.md 2>/dev/null || true
cp "$REGISTER" /logs/artifacts/reserve_disclosure_register.csv 2>/dev/null || true
# ── 归档工作区快照 ──────────────────
# 必须落 /logs/verifier：/logs/artifacts 在判据阶段之前就被采集，这里写的会被丢弃。
_ARCH="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$_ARCH" 2>/dev/null || true
tar czf "$_ARCH/workspace_snapshot.tar.gz" -C "${AGENT_WORKSPACE:-/workspace}" . 2>/dev/null || true

exit 0
