#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/workspace}
OUT=${1:-/workspace/employee_equity_dilution_ledger.xlsx}
python3 "$HERE/solve.py" "$WORKSPACE_ROOT" "$OUT"
