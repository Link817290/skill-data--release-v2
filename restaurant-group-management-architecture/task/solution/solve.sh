#!/usr/bin/env bash
# Replay the authored reference; hidden solution assets stay outside the agent workspace.
set -euo pipefail
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE="${1:-${AGENT_WORKSPACE:-/workspace}}"
mkdir -p "$WORKSPACE/output"
cp "$HERE/reference/control-system-and-long-term-architecture.md" "$WORKSPACE/output/control-system-and-long-term-architecture.md"
