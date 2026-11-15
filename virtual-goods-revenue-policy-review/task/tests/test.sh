#!/usr/bin/env bash
# A judge failure aborts scoring; missing/invalid candidate files are scored by the validator.
set -euo pipefail
SUBMISSION="${1:-/workspace/revenue_policy_review.csv}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACT_OUT="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$OUT" "$ARTIFACT_OUT"
rm -f "$OUT"/reward*.txt "$OUT"/reward*.json
VALIDATOR_PATH="${VALIDATOR_PATH:-$(cd "$(dirname "$0")" && pwd)/validator.py}"
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
cp "$SUBMISSION" "$ARTIFACT_OUT/revenue_policy_review.csv" 2>/dev/null || true
exit 0
