#!/bin/bash
set -uo pipefail
ANSWER="${1:-/workspace/shortlist.xlsx}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
clear_rewards() {
  rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward.json"
}
clear_rewards
rm -f "$OUT/reward_detail.json" "$OUT/verify_result.json" "$OUT/error.json"
infra_error() {
  clear_rewards
  printf '{"status":"UNMEASURED","error":"judge_infrastructure_error"}\n' > "$OUT/error.json"
  cp "$OUT/error.json" "$OUT/verify_result.json"
  cp "$OUT/error.json" "$OUT/reward_detail.json"
  exit 2
}
if ! python3 "$(dirname "$0")/validator.py" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  infra_error
fi
if ! python3 - "$OUT" <<'PY'
import json, math, sys
from pathlib import Path
out = Path(sys.argv[1])
detail = json.loads((out / 'reward_detail.json').read_text())
values = detail['rewards']
if any(type(values[key]) not in (int, float) or not math.isfinite(values[key]) or not 0 <= values[key] <= 1
       for key in ('strict', 'lenient')):
    raise ValueError('invalid numeric rewards')
if values['lenient'] not in (0, 1):
    raise ValueError('completion score must be binary')
for name, value in [('reward', values['strict']), ('reward_strict', values['strict']), ('reward_lenient', values['lenient'])]:
    (out / (name + '.txt')).write_text(str(value) + '\n')
(out / 'reward.json').write_text(json.dumps({'reward': values['strict'], 'reward_strict': values['strict'],
    'reward_lenient': values['lenient']}, indent=2) + '\n')
(out / 'verify_result.json').write_text(json.dumps({'status': detail['status'], 'rewards': values}, indent=2) + '\n')
PY
then
  infra_error
fi
if [ -f "$ANSWER" ]; then
  cp "$ANSWER" "$OUT/shortlist.xlsx" 2>/dev/null || true
  ARTIFACTS="${ARTIFACT_OUTPUT_DIR:-$OUT/artifacts}"
  mkdir -p "$ARTIFACTS"
  cp "$ANSWER" "$ARTIFACTS/shortlist.xlsx"
fi
