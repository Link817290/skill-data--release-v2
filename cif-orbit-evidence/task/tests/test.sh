#!/usr/bin/env bash
set -euo pipefail
SUBMISSION="${1:-/workspace/output/orbit_evidence.json}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward.json"
failure() {
  rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward.json"
  printf '{"status":"UNMEASURED","infrastructure_error":true}\n' > "$OUT/verify_result.json"
  exit 1
}
if ! python3 "$(dirname "$0")/validator.py" "$SUBMISSION" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  failure
fi
if ! python3 - "$OUT" <<'PY'
import json, math, sys
from pathlib import Path
out = Path(sys.argv[1])
detail = json.loads((out / 'reward_detail.json').read_text())
rewards = detail['rewards']
strict, lenient = rewards['strict'], rewards['lenient']
assert all(type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 1 for v in (strict, lenient))
assert lenient in (0, 1)
for name, value in [('reward', strict), ('reward_strict', strict), ('reward_lenient', lenient)]:
    (out / (name + '.txt')).write_text(f'{value:.10f}\n')
(out / 'reward.json').write_text(json.dumps({'reward':strict,'reward_strict':strict,'reward_lenient':lenient}) + '\n')
(out / 'verify_result.json').write_text(json.dumps({'status':'completed','rewards':rewards}) + '\n')
PY
then
  failure
fi
