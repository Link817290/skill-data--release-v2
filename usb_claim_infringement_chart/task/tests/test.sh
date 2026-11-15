#!/bin/bash
set -uo pipefail
ANSWER="${1:-/workspace/claim_chart.json}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"

# Persist a real zero before attempting to read the deliverable.
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"

if [ ! -e "$ANSWER" ]; then
  echo "no deliverable at $ANSWER" > "$OUT/validator.log"
  exit 0
fi

python3 "$HERE/validator.py" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
    strict = float(d['rewards']['strict'])
    lenient = float(d['rewards']['lenient'])
except Exception:
    raise SystemExit(0)
out = sys.argv[2]
open(out + '/reward_strict.txt', 'w').write('%.6f\n' % strict)
open(out + '/reward_lenient.txt', 'w').write('%.6f\n' % lenient)
open(out + '/reward.txt', 'w').write('%.6f\n' % strict)
json.dump({'reward': strict, 'reward_strict': strict, 'reward_lenient': lenient},
          open(out + '/reward.json', 'w'), indent=2)
PY
ARTIFACTS="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS"
cp "$ANSWER" "$ARTIFACTS/claim_chart.json" 2>/dev/null || true
cp "$ANSWER" "$OUT/claim_chart.json" 2>/dev/null || true

if ! python3 "$HERE/mix_judge/apply_semantic.py" --candidate "$ANSWER" --out "$OUT"; then
  exit 2
fi

exit 0
