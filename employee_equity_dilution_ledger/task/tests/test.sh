#!/bin/bash
set -uo pipefail
ANSWER="${1:-/workspace/employee_equity_dilution_ledger.xlsx}"
OUT=/logs/verifier
mkdir -p "$OUT"
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
if [ ! -f "$ANSWER" ]; then echo "no deliverable at $ANSWER" > "$OUT/validator.log"; exit 0; fi
python3 /tests/validator.py "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || true
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json,sys
d={}
try:
 d=json.load(open(sys.argv[1])); r=d.get('rewards',{}); strict=float(r.get('strict',0)); leng=float(r.get('lenient',0))
except Exception as e:
 open(sys.argv[2]+'/validator.log','a').write(str(e)); strict=leng=0.0
out=sys.argv[2]
open(out+'/reward_strict.txt','w').write(f'{strict:.6f}\n'); open(out+'/reward_lenient.txt','w').write(f'{leng:.6f}\n'); open(out+'/reward.txt','w').write(f'{strict:.6f}\n')
payload={'reward':strict,'reward_strict':strict,'reward_lenient':leng}; payload.update(d.get('group_points',{})); json.dump(payload,open(out+'/reward.json','w'),indent=2)
PY
mkdir -p /logs/artifacts && cp "$ANSWER" /logs/artifacts/employee_equity_dilution_ledger.xlsx 2>/dev/null || true
cp "$ANSWER" "$OUT/employee_equity_dilution_ledger.xlsx" 2>/dev/null || true
# ── 归档工作区（判据改动后可离线重评，不必重跑模型）──────────────────
# 必须落 /logs/verifier：/logs/artifacts 在判据阶段之前就被采集，这里写的会被丢弃。
_ARCH="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$_ARCH" 2>/dev/null || true
tar czf "$_ARCH/workspace_snapshot.tar.gz" -C "${AGENT_WORKSPACE:-/workspace}" . 2>/dev/null || true

# --- mix judge (installed by mix_judge.py install) ---
# The program judge above has written its evidence. The required source-bound LLM gate
# settles open owners. A transport or validation failure removes rewards as UNMEASURED.
# Harness conventions only: rewards in $VERIFIER_OUTPUT_DIR, the deliverable root is this
# script's first argument (else $AGENT_WORKSPACE, else /workspace), the gate beside this script.
MJ_OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
MJ_ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
MJ_DIR="$(cd "$(dirname "$0")" && pwd)/mix_judge"
if [ -f "$MJ_DIR/gate_runtime.py" ] && [ -f "$MJ_OUT/reward_detail.json" ]; then
  cp "$MJ_OUT/reward_detail.json" "$MJ_OUT/program_reward_detail.json"
  python3 "$MJ_DIR/gate_runtime.py" score --installed "$MJ_DIR" \
    --deliverable-dir "$MJ_ROOT" --program-detail "$MJ_OUT/program_reward_detail.json" \
    --out "$MJ_OUT" >> "$MJ_OUT/mix_judge.log" 2>&1 || true
fi

exit 0
