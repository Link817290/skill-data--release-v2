#!/usr/bin/env bash
set -uo pipefail

ANSWER="${1:-/workspace/output/citation_reconciliation.md}"
OUT="${VERIFIER_OUT:-${VERIFIER_OUTPUT_DIR:-/logs/verifier}}"
ARTIFACTS="${ARTIFACTS_OUT:-/logs/artifacts}"
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p "$OUT"
if ! mkdir -p "$ARTIFACTS" 2>/dev/null; then
  ARTIFACTS="$OUT/artifacts"
  mkdir -p "$ARTIFACTS"
fi
rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward.json" "$OUT/verify_result.json"

business_zero() {
  printf '0.000000\n' > "$OUT/reward.txt"
  cp "$OUT/reward.txt" "$OUT/reward_strict.txt"
  cp "$OUT/reward.txt" "$OUT/reward_lenient.txt"
  printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
  printf '{"status":"completed","rewards":{"strict":0,"lenient":0}}\n' > "$OUT/verify_result.json"
  exit 0
}

judge_error() {
  rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward.json"
  printf '{"status":"judge_infrastructure_error"}\n' > "$OUT/verify_result.json"
  exit 1
}

[ -f "$ANSWER" ] || business_zero
if ! python3 -B "$HERE/validator.py" "$ANSWER" "${AGENT_WORKSPACE:-/workspace}" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  judge_error
fi
if ! python3 -B - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, math, sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
rewards=data['rewards']
for key in ('strict','lenient'):
    value=rewards[key]
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('invalid reward')
out=Path(sys.argv[2])
for name,key in (('reward.txt','strict'),('reward_strict.txt','strict'),('reward_lenient.txt','lenient')):
    (out/name).write_text(f'{rewards[key]:.6f}\n')
payload={'reward':rewards['strict'],'reward_strict':rewards['strict'],'reward_lenient':rewards['lenient']}
(out/'reward.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
(out/'verify_result.json').write_text(json.dumps({'status':'completed','rewards':rewards},indent=2)+'\n')
PY
then
  judge_error
fi
cp "$ANSWER" "$ARTIFACTS/citation_reconciliation.md" || true
