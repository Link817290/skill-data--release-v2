#!/usr/bin/env bash
set -euo pipefail

export LANG=C
export LC_ALL=C
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACT_OUT="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$OUT" "$ARTIFACT_OUT"
printf 'UNMEASURED\n' > "$OUT/reward.txt"
printf 'UNMEASURED\n' > "$OUT/reward_strict.txt"
printf 'UNMEASURED\n' > "$OUT/reward_lenient.txt"
printf '{"measurement_status":"UNMEASURED","reward":null,"reward_strict":null,"reward_lenient":null}\n' > "$OUT/reward.json"
printf '{"measurement_status":"UNMEASURED","infrastructure_error":"verifier did not complete"}\n' > "$OUT/reward_detail.json"

python3 -m pytest -c /dev/null -p no:cacheprovider "$SCRIPT_DIR/test_outputs.py" -rA -v
cp /workspace/build_report.json "$ARTIFACT_OUT/build_report.json" 2>/dev/null || true
cp /workspace/analysis/diagnosis.md "$ARTIFACT_OUT/diagnosis.md" 2>/dev/null || true
cp /workspace/patches/patch_0.diff "$ARTIFACT_OUT/patch_0.diff" 2>/dev/null || true
