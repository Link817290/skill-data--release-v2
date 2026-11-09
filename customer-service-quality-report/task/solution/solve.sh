#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${1:-${AGENT_WORKSPACE:-${WORKSPACE_ROOT:-/workspace}}}"
mkdir -p "$WS/output"
cp "$HERE/../../golden/service-quality-report.xlsx" "$WS/output/service-quality-report.xlsx"
