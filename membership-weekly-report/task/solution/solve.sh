#!/usr/bin/env bash
# Replay the accepted authored reference; it is not copied into the actor image.
set -euo pipefail

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE="${1:-${AGENT_WORKSPACE:-/workspace}}"
mkdir -p "$WORKSPACE/output"
cp "$HERE/reference/weekly_report.docx" "$WORKSPACE/output/weekly_report.docx"
