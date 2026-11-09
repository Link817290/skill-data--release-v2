#!/bin/bash
set -uo pipefail
ANSWER="${1:-/workspace/regime_map.xlsx}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"

rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward.json"

judge_error() {
  rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward.json"
  printf '{"status":"UNMEASURED","infrastructure_error":true}\n' > "$OUT/verify_result.json"
  exit 1
}

if [ ! -f "$ANSWER" ]; then
  printf '0\n' > "$OUT/reward_strict.txt"
  printf '0\n' > "$OUT/reward_lenient.txt"
  printf '0\n' > "$OUT/reward.txt"
  printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
  printf '{"status":"missing_deliverable"}\n' > "$OUT/verify_result.json"
  echo "no deliverable at $ANSWER" | tee "$OUT/validator.log"
  exit 0
fi

if ! python3 "$(dirname "$0")/validator.py" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  # An API/protocol outage is not a failed market judgement.
  judge_error
fi
if ! python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, math, sys
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
    rewards = d['rewards']
    strict = float(rewards['strict'])
    lenient = float(rewards['lenient'])
    if any(isinstance(rewards[key], bool) for key in ('strict', 'lenient')) or not all(math.isfinite(value) and 0 <= value <= 1 for value in (strict, lenient)):
        raise ValueError('invalid reward values')
    if lenient not in (0.0, 1.0):
        raise ValueError('lenient must be binary')
except Exception as exc:
    sys.stderr.write('could not read reward: %s\n' % exc); raise SystemExit(1)
OUT = sys.argv[2]
# Two co-equal standards, one file each.
open(OUT + '/reward_strict.txt', 'w').write('%.6f\n' % strict)
open(OUT + '/reward_lenient.txt', 'w').write('%.6f\n' % lenient)
# reward.txt mirrors the strict standard so a single-scalar consumer (Harbor)
# keeps reading a number; it is not a third score.
open(OUT + '/reward.txt', 'w').write('%.6f\n' % strict)
payload = {'reward': strict, 'reward_strict': strict, 'reward_lenient': lenient}
for key, value in (d.get('dimension_scores') or {}).items():
    payload[key] = float(value)
json.dump(payload, open(OUT + '/reward.json', 'w'), indent=2)
json.dump({'status': 'completed', 'rewards': rewards}, open(OUT + '/verify_result.json', 'w'), indent=2)
PY
then
  judge_error
fi
cp "$ANSWER" "$OUT/regime_map.xlsx" 2>/dev/null || true
ARTIFACTS="${VERIFIER_ARTIFACT_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS" && cp "$ANSWER" "$ARTIFACTS/regime_map.xlsx" 2>/dev/null || true
exit 0
