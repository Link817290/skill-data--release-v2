#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/workspace}
answer="${1:-/workspace/review.xlsx}"
mkdir -p "$(dirname "$answer")"
python3 "$HERE/generate_golden.py" "$answer"
