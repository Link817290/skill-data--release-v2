#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${1:-/workspace}"
if [ "$#" -gt 0 ]; then shift; fi
exec python3 -B "$HERE/verify.py" "$WORKSPACE" --output "${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}" --mode "${LLM_JUDGE_MODE:-fresh}" "$@"
