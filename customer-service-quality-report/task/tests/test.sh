#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${1:-${AGENT_WORKSPACE:-${WORKSPACE_ROOT:-/workspace}}}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
rm -f "$OUT/reward.json" "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt" "$OUT/reward_detail.json"
python3 "$HERE/validator.py" "$WS" --out "$OUT"
python3 "$HERE/mix_judge/apply.py" --submission-dir "$WS/output" --verifier-dir "$OUT"
