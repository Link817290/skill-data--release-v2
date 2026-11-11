#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/workspace}
OUTPUT=${1:-/workspace/alert_review.json}
python3 "$HERE/reference_solution.py" --workspace "$WORKSPACE_ROOT" --output "$OUTPUT"
