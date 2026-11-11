#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUTPUT_DIR=${1:-/workspace/deliverables}
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/workspace}
python3 "$HERE/build_reference.py" \
  --workspace "$WORKSPACE_ROOT" \
  --output-dir "$OUTPUT_DIR"
