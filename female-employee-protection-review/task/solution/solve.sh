#!/usr/bin/env bash
set -euo pipefail
WS="${1:-${AGENT_WORKSPACE:-/workspace}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$WS/output"
cp "$HERE/../../golden/audit.xlsx" "$WS/output/audit.xlsx"
cp "$HERE/../../golden/report.docx" "$WS/output/report.docx"
cp "$HERE/../../golden/actions.xlsx" "$WS/output/actions.xlsx"
