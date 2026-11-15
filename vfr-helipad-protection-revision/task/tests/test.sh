#!/usr/bin/env bash
# A judge failure aborts scoring; missing/invalid candidate files are scored by the validator.
set -euo pipefail
SUBMISSION="${1:-/workspace/output}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACT_OUT="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$OUT" "$ARTIFACT_OUT"
rm -f "$OUT"/reward*.txt "$OUT"/reward*.json
VALIDATOR_PATH="${VALIDATOR_PATH:-$(cd "$(dirname "$0")" && pwd)/validator.py}"
if [[ -f "$SUBMISSION" ]]; then SUBMISSION="$(dirname "$SUBMISSION")"; elif [[ -d "$SUBMISSION/output" ]]; then SUBMISSION="$SUBMISSION/output"; fi
if ! python3 "$VALIDATOR_PATH" "$SUBMISSION" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  rm -f "$OUT"/reward*.txt "$OUT"/reward*.json
  echo 'Required validator/judge failed; trial is unscorable' >&2
  exit 2
fi
if ! python3 - "$OUT" <<'PUBLISH'
import json,sys,math
from pathlib import Path
out=Path(sys.argv[1]);d=json.loads((out/'reward_detail.json').read_text());a=float(d['rewards']['strict']);b=float(d['rewards']['lenient'])
assert all(math.isfinite(x) and 0<=x<=1 for x in (a,b))
for name,value in [('reward',a),('reward_strict',a),('reward_lenient',b)]: (out/(name+'.txt')).write_text(f'{value:.8f}\n')
payload={'reward':a,'reward_strict':a,'reward_lenient':b}
payload.update({k:float(v) for k,v in d.get('group_points',{}).items()})
(out/'reward.json').write_text(json.dumps(payload,indent=2)+'\n')
PUBLISH
then
  rm -f "$OUT"/reward*.txt "$OUT"/reward*.json
  exit 2
fi
for artifact in inspection_report.json repaired_plan.dxf repair_memo.md; do
  if [[ -f "$SUBMISSION/$artifact" ]]; then
    cp "$SUBMISSION/$artifact" "$ARTIFACT_OUT/$artifact" 2>/dev/null || true
  fi
done
# ── 归档工作区，供离线复核 ──────────────────────────────────────────
# 必须落 /logs/verifier：/logs/artifacts 在判据阶段之前就被采集，这里写的会被丢弃。
_ARCH="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$_ARCH" 2>/dev/null || true
tar czf "$_ARCH/workspace_snapshot.tar.gz" -C "${AGENT_WORKSPACE:-/workspace}" . 2>/dev/null || true

# --- mix judge (installed by mix_judge.py install) ---
# The program judge above has written its verdict. The LLM gate may zero it (gaming,
# or breaking the task text); otherwise it stands. If the LLM cannot be reached the
# program judge's verdict stands. The program judge's own detail is kept beside it.
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
