#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
python3 -B "$HERE/validator.py" "$ROOT/output" --json "$OUT/program_detail.json"
STATUS=$?
python3 -B - "$OUT" "$STATUS" <<'PY'
import json,math,sys
from pathlib import Path
p=Path(sys.argv[1])
if int(sys.argv[2]):
    (p/'verifier_status.json').write_text('{"verifier_status":"error"}')
    raise SystemExit(1)
d=json.loads((p/'program_detail.json').read_text())
strict=d['reward_strict'];lenient=d['reward_lenient']
assert all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in (strict,lenient))
for name,value in [('reward.txt',strict),('reward_strict.txt',strict),('reward_lenient.txt',lenient)]:
    (p/name).write_text(f'{value:.9f}\n')
(p/'reward.json').write_text(json.dumps({'reward':strict,'reward_strict':strict,'reward_lenient':lenient}))
(p/'reward_detail.json').write_text(json.dumps(d,ensure_ascii=False))
(p/'verifier_status.json').write_text('{"verifier_status":"ok"}')
PY
RESULT=$?
if [ "$RESULT" -eq 0 ]; then
    python3 -B "$HERE/mix_judge/apply.py" --submission-dir "$ROOT/output" --verifier-dir "$OUT" || RESULT=$?
fi
if [ -d "$ROOT/output" ] && [ -n "${ARTIFACT_OUTPUT_DIR:-}" ]; then
    mkdir -p "$ARTIFACT_OUTPUT_DIR"
    find "$ROOT/output" -maxdepth 1 -type f -name '*.docx' -exec cp {} "$ARTIFACT_OUTPUT_DIR/" \;
fi
exit "$RESULT"
