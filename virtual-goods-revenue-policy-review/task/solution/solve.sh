#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT=${1:-/workspace/revenue_policy_review.csv}
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/workspace}
python3 "$HERE/reference_solution.py" --workspace "$WORKSPACE_ROOT" --output "$OUT"
