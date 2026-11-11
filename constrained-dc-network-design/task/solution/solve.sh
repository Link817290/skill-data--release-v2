#!/bin/sh
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/workspace}
SOURCE=${SOURCE:-"$WORKSPACE_ROOT/Supply chain logisitcs problem.xlsx"}
OUTPUT=${1:-"$WORKSPACE_ROOT/network_design_recommendation.xlsx"}

python3 "$HERE/reference_solution.py" --source "$SOURCE" --output "$OUTPUT"
