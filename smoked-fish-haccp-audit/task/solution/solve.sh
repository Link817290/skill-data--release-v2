#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/workspace}
OUTPUT=${1:-/workspace/haccp_audit.json}
python3 "$HERE/reference_solution.py" "$WORKSPACE_ROOT" "$OUTPUT"
