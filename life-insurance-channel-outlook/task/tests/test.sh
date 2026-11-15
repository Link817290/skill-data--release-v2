#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
python3 -B "$HERE/validator.py" "$ROOT/output" > "$OUT/program_detail.json" 2> "$OUT/validator.stderr.log"
STATUS=$?
python3 -B - "$OUT" "$STATUS" <<'PY'
import json, math, sys
from pathlib import Path
out=Path(sys.argv[1])
try:
    if int(sys.argv[2]): raise RuntimeError('Program Judge failed; see validator.stderr.log')
    detail=json.loads((out/'program_detail.json').read_text(encoding='utf-8'))
    strict=detail['final_score']
    lenient=detail['reward_lenient']
    for value in (strict,lenient):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
            raise ValueError('Invalid program score')
except Exception as error:
    (out/'verifier_status.json').write_text(json.dumps({'verifier_status':'error','error':str(error)}))
    for name in ('reward.json','reward.txt','reward_strict.txt','reward_lenient.txt'):
        (out/name).unlink(missing_ok=True)
    raise SystemExit(1)
for name,value in [('reward.txt',strict),('reward_strict.txt',strict),('reward_lenient.txt',lenient)]:
    (out/name).write_text(f'{value:.9f}\n',encoding='utf-8')
(out/'reward.json').write_text(json.dumps({'reward':strict,'reward_strict':strict,'reward_lenient':lenient})+'\n',encoding='utf-8')
(out/'reward_detail.json').write_text(json.dumps(detail,ensure_ascii=False),encoding='utf-8')
(out/'verifier_status.json').write_text('{"verifier_status":"ok"}\n',encoding='utf-8')
PY
REWARD_STATUS=$?
if [ "$REWARD_STATUS" -eq 0 ]; then
    python3 -B "$HERE/mix_judge/apply.py" --submission-dir "$ROOT/output" --verifier-dir "$OUT" || REWARD_STATUS=$?
fi
if [ -d "$ROOT/output" ] && [ -n "${ARTIFACT_OUTPUT_DIR:-}" ]; then
    mkdir -p "$ARTIFACT_OUTPUT_DIR"
    find "$ROOT/output" -maxdepth 1 -type f -name '*.pdf' -exec cp {} "$ARTIFACT_OUTPUT_DIR/" \;
fi
exit "$REWARD_STATUS"
