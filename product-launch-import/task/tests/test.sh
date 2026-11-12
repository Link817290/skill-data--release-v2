#!/bin/sh
set -eu
OUT=/logs/verifier
mkdir -p "$OUT"
if ! python -c 'import fitz' >/dev/null 2>&1; then
  printf '{"status":"unmeasured","measurement_complete":false,"measurement_error":"PyMuPDF dependency unavailable"}\n' > "$OUT/verifier_status.json"
  exit 2
fi
if [ ! -d /workspace/output ]; then
  printf '{"status":"unmeasured","measurement_complete":false,"measurement_error":"submission directory unavailable"}\n' > "$OUT/verifier_status.json"
  exit 2
fi
if [ -n "${SEMANTIC_REPLAY:-}" ] && [ ! -f "$SEMANTIC_REPLAY" ]; then
  printf '{"status":"unmeasured","measurement_complete":false,"measurement_error":"semantic replay entity unavailable"}\n' > "$OUT/verifier_status.json"
  exit 2
fi
set +e
set -- python "$(dirname "$0")/evaluate.py" --submission-dir /workspace/output --out /logs/verifier/current
if [ -n "${SEMANTIC_REPLAY:-}" ]; then set -- "$@" --semantic-replay "$SEMANTIC_REPLAY"; fi
"$@"; code=$?
set -e
python - <<'PY'
import json
from pathlib import Path
p=Path('/logs/verifier/current/result.json');d=json.loads(p.read_text());s=d.get('score');l=d.get('reward_lenient',float(bool(s is not None and s>=0.40)))
out={'reward':s,'reward_strict':s,'reward_lenient':l,'score':s,'measurement_complete':d.get('measurement_complete',False),'rewards':{'strict':s,'lenient':l}}
Path('/logs/verifier/reward.json').write_text(json.dumps(out,indent=2)+'\n')
Path('/logs/verifier/reward.txt').write_text(str(s)+'\n')
Path('/logs/verifier/reward_strict.txt').write_text(str(s)+'\n')
Path('/logs/verifier/reward_lenient.txt').write_text(str(l)+'\n')
PY
exit "$code"
