#!/usr/bin/env bash
set -euo pipefail
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
rm -f "$OUT"/reward.json "$OUT"/reward.txt "$OUT"/reward_strict.txt "$OUT"/reward_lenient.txt
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! python3 -B "$HERE/validator.py" "${1:-/workspace}" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  printf '{"status":"UNMEASURED","error":"verifier infrastructure failed; see validator.log"}\n' > "$OUT/status.json"
  exit 1
fi
python3 - "$OUT" <<'PY'
import json,sys,math
from pathlib import Path
p=Path(sys.argv[1]);d=json.loads((p/'reward_detail.json').read_text());s=d['rewards']['strict'];l=d['rewards']['lenient']
assert all(isinstance(x,(int,float)) and math.isfinite(x) and 0<=x<=1 for x in [s,l])
(p/'reward.json').write_text(json.dumps({'reward':s,'reward_strict':s,'reward_lenient':l})+'\n')
for name,value in [('reward',s),('reward_strict',s),('reward_lenient',l)]: (p/(name+'.txt')).write_text(str(value)+'\n')
(p/'status.json').write_text(json.dumps({'status':d['status']})+'\n')
PY
