#!/usr/bin/env bash
# Replay the authored reference; hidden solution assets stay outside the agent workspace.
set -euo pipefail
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE="${1:-${AGENT_WORKSPACE:-/workspace}}"
mkdir -p "$WORKSPACE/artifacts"
cp "$HERE/reference/质证意见.docx" "$WORKSPACE/artifacts/质证意见.docx"
