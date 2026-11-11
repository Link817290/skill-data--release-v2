#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/workspace}
OUTPUT_DIR=${1:-/workspace/output}
mkdir -p "$OUTPUT_DIR"
python3 "$HERE/solve.py" --workspace "$WORKSPACE_ROOT" --output-dir "$OUTPUT_DIR"
