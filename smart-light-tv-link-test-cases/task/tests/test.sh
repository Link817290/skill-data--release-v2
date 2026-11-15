#!/usr/bin/env bash
set -euo pipefail
WS="${1:-${AGENT_WORKSPACE:-/workspace}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}"
mkdir -p "$LOGS"
python3 "$HERE/validator.py" --workspace "$WS" --log-dir "$LOGS"
if [ -f "$WS/output/linkage-test-cases.xlsx" ]; then
    cp "$WS/output/linkage-test-cases.xlsx" "$LOGS/submitted-linkage-test-cases.xlsx"
fi
