#!/usr/bin/env bash
set -uo pipefail
SUBMISSION="${1:-/workspace/output/seismic_catalogue_report.json}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACT_OUT="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$OUT" "$ARTIFACT_OUT"
printf '0\n' > "$OUT/reward.txt"
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
python3 "$(dirname "$0")/validator.py" "$SUBMISSION" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || true
ARTIFACT_TARGET="$ARTIFACT_OUT/seismic_catalogue_report.json" python3 - "$OUT/reward_detail.json" "$OUT" "$SUBMISSION" <<'PY'
import json, pathlib, shutil, sys
detail_path, out, submission = sys.argv[1:]
try:
    detail = json.loads(pathlib.Path(detail_path).read_text())
    value = float(detail.get('reward_strict', detail.get('reward', 0.0)))
    lenient = float(detail.get('reward_lenient', 0.0))
except Exception:
    value, lenient = 0.0, 0.0
for name in ('reward.txt','reward_strict.txt'):
    pathlib.Path(out, name).write_text(f'{value:.6f}\n')
pathlib.Path(out,'reward_lenient.txt').write_text(f'{lenient:.6f}\n')
pathlib.Path(out,'reward.json').write_text(json.dumps(
    {'reward':value,'reward_strict':value,'reward_lenient':lenient}, indent=2)+'\n')
try:
    p=pathlib.Path(submission)
    target=pathlib.Path(__import__('os').environ['ARTIFACT_TARGET'])
    if p.is_file(): shutil.copy2(p, target)
except Exception: pass
PY
# ── 归档工作区（判据改动后可离线重评，不必重跑模型）──────────────────
# 必须落 /logs/verifier：/logs/artifacts 在判据阶段之前就被采集，这里写的会被丢弃。
_ARCH="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$_ARCH" 2>/dev/null || true
tar czf "$_ARCH/workspace_snapshot.tar.gz" -C "${AGENT_WORKSPACE:-/workspace}" . 2>/dev/null || true

exit 0
