#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE=${1:-/workspace}
python3 "$SCRIPT_DIR/reference_solution.py" "$WORKSPACE"
