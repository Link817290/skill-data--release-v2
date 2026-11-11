#!/bin/sh
set -eu
OUT=${1:-${OUTPUT_DIR:-/workspace/output}}
python -B "$(dirname "$0")/solve.py" --out "$OUT"
