#!/usr/bin/env bash
set -euo pipefail

python3 "$(dirname "$0")/solve.py" "${WORKSPACE_ROOT:-/workspace}"
