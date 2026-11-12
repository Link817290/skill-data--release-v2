#!/usr/bin/env bash
set -euo pipefail
ROOT="${AGENT_WORKSPACE:-/workspace}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/output"
cp "$HERE/../../golden/jurisdiction.docx" "$ROOT/output/jurisdiction.docx"
cp "$HERE/../../golden/feng-request.docx" "$ROOT/output/feng-request.docx"
cp "$HERE/../../golden/tian-request.docx" "$ROOT/output/tian-request.docx"
