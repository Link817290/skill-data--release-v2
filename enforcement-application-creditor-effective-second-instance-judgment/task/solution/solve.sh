#!/usr/bin/env bash
# Replay the authored reference; hidden solution assets stay outside the agent workspace.
set -euo pipefail
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE="${1:-${AGENT_WORKSPACE:-/workspace}}"
mkdir -p "$WORKSPACE/artifacts"
cp "$HERE/reference/执行申请书.docx" "$WORKSPACE/artifacts/执行申请书.docx"
