#!/usr/bin/env bash
set -euo pipefail
WS="${1:-${AGENT_WORKSPACE:-${WORKSPACE_ROOT:-/workspace}}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$WS/output"
cp -- "$HERE/../../golden/execution-plan.docx" "$WS/output/execution-plan.docx"
