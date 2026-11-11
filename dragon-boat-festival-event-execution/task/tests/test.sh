#!/usr/bin/env bash
set -euo pipefail
WS="${1:-${AGENT_WORKSPACE:-${WORKSPACE_ROOT:-/workspace}}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}"
mkdir -p "$LOGS"
rm -f -- "$LOGS/reward.json" "$LOGS/reward.txt" "$LOGS/reward_strict.txt" "$LOGS/reward_lenient.txt" "$LOGS/reward_detail.json"
python3 -B "$HERE/validator.py" "$WS" --check-protected-inputs --logs "$LOGS"
mkdir -p "$LOGS/output"
if [ -f "$WS/output/execution-plan.docx" ]; then
    cp "$WS/output/execution-plan.docx" "$LOGS/output/execution-plan.docx"
fi
