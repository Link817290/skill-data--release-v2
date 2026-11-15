#!/bin/sh
set -eu
python "$(dirname "$0")/solve.py" "${1:-/workspace/output}"
