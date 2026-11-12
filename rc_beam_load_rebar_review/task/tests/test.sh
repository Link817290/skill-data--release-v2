#!/usr/bin/env bash
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
ANSWER="${1:-/workspace/beam_review.xlsx}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
# The package carries the exact Golden semantic response.  A verifier replay
# can therefore run without network; a changed candidate gets a new request
# identity and is judged live when the configured mode permits it.
if [ -d /golden_replay ]; then
  CACHE_DIR="${LLM_JUDGE_CACHE_DIR:-/logs/verifier/judge-cache}"
  mkdir -p "$CACHE_DIR"
  cp /golden_replay/*.json "$CACHE_DIR"/ 2>/dev/null || true
fi
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
if [ ! -f "$ANSWER" ]; then echo "no deliverable at $ANSWER" > "$OUT/validator.log"; exit 0; fi
python3 "$(dirname "$0")/validator.py" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || abort_scoring
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json,sys
out=sys.argv[2]
try:
 d=json.load(open(sys.argv[1],encoding='utf-8')); r=d.get('rewards',{})
 strict=float(r.get('strict',0)); length=float(r.get('lenient',0))
except Exception as e:
 open(out+'/validator.log','a').write('reward parse failed: %s\n'%e); raise SystemExit(2)
open(out+'/reward_strict.txt','w').write('%.6f\n'%strict)
open(out+'/reward_lenient.txt','w').write('%.6f\n'%length)
open(out+'/reward.txt','w').write('%.6f\n'%strict)
json.dump({'reward':strict,'reward_strict':strict,'reward_lenient':length},open(out+'/reward.json','w'),indent=2)
PY
mkdir -p /logs/artifacts
cp "$ANSWER" "$OUT/beam_review.xlsx" 2>/dev/null || true
cp "$ANSWER" /logs/artifacts/beam_review.xlsx 2>/dev/null || true
# ── 归档工作区快照 ─────────────────────────────
# 必须落 /logs/verifier：/logs/artifacts 在判据阶段之前就被采集，这里写的会被丢弃。
_ARCH="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$_ARCH" 2>/dev/null || true
tar czf "$_ARCH/workspace_snapshot.tar.gz" -C "${AGENT_WORKSPACE:-/workspace}" . 2>/dev/null || true

exit 0
