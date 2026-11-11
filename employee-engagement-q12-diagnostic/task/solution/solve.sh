#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE="${1:-/workspace}"
if [ ! -d "$WORKSPACE/materials" ]; then
  WORKSPACE="$SCRIPT_DIR/../environment/workspace"
fi

mkdir -p "$WORKSPACE/output"
python3 "$SCRIPT_DIR/q12_pipeline.py" \
  --materials "$WORKSPACE/materials" \
  --output "$WORKSPACE/output"
