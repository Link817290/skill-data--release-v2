#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT=/logs/verifier
rm -rf "$OUT/current"
mkdir -p "$OUT/current"
status=0
if [ -n "${SEMANTIC_REPLAY:-}" ]; then
  python -B "$HERE/evaluate.py" --submission-dir /workspace/output --out "$OUT/current/evaluation" --semantic-replay "$SEMANTIC_REPLAY" || status=$?
else
  python -B "$HERE/evaluate.py" --submission-dir /workspace/output --out "$OUT/current/evaluation" || status=$?
fi
if [ "$status" -gt 1 ]; then exit "$status"; fi
python - "$OUT/current" <<'PY'
import json,pathlib,sys
out=pathlib.Path(sys.argv[1]);detail=json.loads((out/'evaluation/result.json').read_text())
strict=float(detail.get('reward_strict',detail.get('score',0.0)));lenient=float(detail.get('reward_lenient',0.0))
(out/'reward_detail.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'reward.txt').write_text(f'{strict:.12f}\n',encoding='utf-8')
(out/'reward_strict.txt').write_text(f'{strict:.12f}\n',encoding='utf-8')
(out/'reward_lenient.txt').write_text(f'{lenient:.6f}\n',encoding='utf-8')
(out/'reward.json').write_text(json.dumps({'reward':strict,'reward_strict':strict,'reward_lenient':lenient})+'\n',encoding='utf-8')
PY
