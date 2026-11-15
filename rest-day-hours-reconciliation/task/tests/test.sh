#!/usr/bin/env bash
set -euo pipefail
WS="${1:-${AGENT_WORKSPACE:-/workspace}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}"
mkdir -p "$LOGS"
python3 "$HERE/validator.py" --workspace "$WS" --log-dir "$LOGS"
test -s "$LOGS/reward.json"
for name in rest-day-review.xlsx review-conclusions.txt; do
    if [ -f "$WS/output/$name" ]; then
        cp "$WS/output/$name" "$LOGS/submitted-$name"
    fi
done
