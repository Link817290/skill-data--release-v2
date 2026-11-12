#!/usr/bin/env bash
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
printf '{"verifier_status":"started"}\n' > "$OUT/verifier_status.json"

python3 -B "$HERE/validator.py" "$ROOT/output" \
    > "$OUT/program_detail.json" 2> "$OUT/validator.stderr.log"
STATUS=$?
python3 -B - "$OUT" "$STATUS" <<'PY'
import json
import sys
from pathlib import Path
out = Path(sys.argv[1])
try:
    if int(sys.argv[2]):
        raise RuntimeError('Program Judge failed; see validator.stderr.log')
    detail = json.loads((out / 'program_detail.json').read_text(encoding='utf-8'))
    reward = detail['final_score']
    lenient = detail['reward_lenient']
    if isinstance(reward, bool) or not isinstance(reward, (int, float)) or not 0 <= reward <= 1:
        raise ValueError('Invalid reward')
    status = 'ok'
except Exception as exc:
    (out / 'verifier_error.txt').write_text(str(exc), encoding='utf-8')
    (out / 'verifier_status.json').write_text(json.dumps({'verifier_status': 'error', 'error': str(exc)}) + '\n', encoding='utf-8')
    for filename in ('reward.json', 'reward.txt', 'reward_strict.txt', 'reward_lenient.txt'):
        (out / filename).unlink(missing_ok=True)
    raise SystemExit(1)
for filename in ('reward.txt', 'reward_strict.txt'):
    (out / filename).write_text(f'{reward:.6f}\n', encoding='utf-8')
(out / 'reward_lenient.txt').write_text(f'{lenient:.6f}\n', encoding='utf-8')
(out / 'reward.json').write_text(json.dumps({'reward': reward, 'reward_strict': reward, 'reward_lenient': lenient}) + '\n', encoding='utf-8')
(out / 'verifier_status.json').write_text(json.dumps({'verifier_status': status}) + '\n', encoding='utf-8')
(out / 'reward_detail.json').write_text(json.dumps(detail, ensure_ascii=False), encoding='utf-8')
PY
REWARD_STATUS=$?
if [ "$REWARD_STATUS" -eq 0 ]; then
    python3 -B "$HERE/mix_judge/apply.py" --submission-dir "$ROOT/output" --verifier-dir "$OUT" || REWARD_STATUS=$?
fi
if [ -d "$ROOT/output" ] && [ -n "${ARTIFACT_OUTPUT_DIR:-}" ]; then
    mkdir -p "$ARTIFACT_OUTPUT_DIR"
    find "$ROOT/output" -maxdepth 1 -type f -name '*.docx' -exec cp {} "$ARTIFACT_OUTPUT_DIR/" \;
fi
exit "$REWARD_STATUS"
