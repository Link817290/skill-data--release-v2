#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE="${1:-${AGENT_WORKSPACE:-/workspace}}"
if [ ! -d "$WORKSPACE/materials" ]; then
  WORKSPACE="$SCRIPT_DIR/../environment/workspace"
fi

mkdir -p "$WORKSPACE/output"
cp "$SCRIPT_DIR/reference_outputs/"* "$WORKSPACE/output/"
