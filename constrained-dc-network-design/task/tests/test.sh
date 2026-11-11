#!/bin/bash
set -euo pipefail

ANSWER="${1:-/workspace/network_design_recommendation.xlsx}"
SOURCE="/workspace/Supply chain logisitcs problem.xlsx"
OUT=/logs/verifier
mkdir -p "$OUT"

printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"

if [ ! -f "$ANSWER" ]; then
  echo "no deliverable at $ANSWER" > "$OUT/validator.log"
  exit 0
fi

python3 /tests/validator.py "$ANSWER" --source "$SOURCE" --ground-truth /tests/ground_truth.json \
  > "$OUT/reward_detail.json" 2> "$OUT/validator.log"

python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json
import sys

detail_path, out_dir = sys.argv[1:]
try:
    detail = json.load(open(detail_path, encoding="utf-8"))
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"]["lenient"])
except Exception as exc:
    sys.stderr.write(f"could not read verifier detail: {exc}\n")
    raise SystemExit(0)

open(out_dir + "/reward_strict.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
open(out_dir + "/reward_lenient.txt", "w", encoding="utf-8").write(f"{lenient:.6f}\n")
open(out_dir + "/reward.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
payload = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
for key, value in detail.get("group_points", {}).items():
    payload[key] = float(value)
json.dump(payload, open(out_dir + "/reward.json", "w", encoding="utf-8"), indent=2)
PY

cp "$ANSWER" "$OUT/network_design_recommendation.xlsx" 2>/dev/null || true
mkdir -p /logs/artifacts
cp "$ANSWER" /logs/artifacts/network_design_recommendation.xlsx 2>/dev/null || true
# ── 归档工作区（判据改动后可离线重评，不必重跑模型）──────────────────
# 必须落 /logs/verifier：/logs/artifacts 在判据阶段之前就被采集，这里写的会被丢弃。
_ARCH="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$_ARCH" 2>/dev/null || true
tar czf "$_ARCH/workspace_snapshot.tar.gz" -C "${AGENT_WORKSPACE:-/workspace}" . 2>/dev/null || true

# --- mix judge (installed by mix_judge.py install) ---
# The program judge above has written its closed-form verdict. The required LLM
# judge settles the source-bound open explanation owners. A judge failure is
# UNMEASURED and exits nonzero; it never preserves a program-only semantic score.
# Harness conventions only: rewards in $VERIFIER_OUTPUT_DIR, the deliverable root is this
# script's first argument (else $AGENT_WORKSPACE, else /workspace), the gate beside this script.
MJ_OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
MJ_ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
MJ_DIR="$(cd "$(dirname "$0")" && pwd)/mix_judge"
if [ -f "$MJ_DIR/gate_runtime.py" ] && [ -f "$MJ_OUT/reward_detail.json" ]; then
  cp "$MJ_OUT/reward_detail.json" "$MJ_OUT/program_reward_detail.json"
  python3 "$MJ_DIR/gate_runtime.py" score --installed "$MJ_DIR" \
    --deliverable-dir "$MJ_ROOT" --program-detail "$MJ_OUT/program_reward_detail.json" \
    --out "$MJ_OUT" >> "$MJ_OUT/mix_judge.log" 2>&1 || exit 2
fi

exit 0
