#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACTS="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT" "$ARTIFACTS"
rm -f "$OUT/reward.json" "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt"
python3 -B "$HERE/validator.py" "$ROOT" > "$OUT/reward_detail.json"
python3 -B - "$OUT" <<'PY'
import json,sys
from pathlib import Path
out=Path(sys.argv[1])
result=json.loads((out/'reward_detail.json').read_text('utf-8'))
strict=result['rewards']['strict']
lenient=result['rewards']['lenient']
for name,value in [('reward.txt',strict),('reward_strict.txt',strict),('reward_lenient.txt',lenient)]:
    (out/name).write_text(f'{value:.9f}\n','utf-8')
(out/'reward.json').write_text(json.dumps({'reward':strict,'reward_strict':strict,'reward_lenient':lenient})+'\n','utf-8')
PY
if [ -f "$ROOT/output/LG_AKB76043105_Test_Case_List_EN.xlsx" ]; then
  cp "$ROOT/output/LG_AKB76043105_Test_Case_List_EN.xlsx" "$ARTIFACTS/"
fi
tar czf "$OUT/workspace_snapshot.tar.gz" -C "$ROOT" . 2>/dev/null || true
