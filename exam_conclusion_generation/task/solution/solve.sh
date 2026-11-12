#!/usr/bin/env bash
set -euo pipefail

SOLUTION_DIR="${SOLUTION_DIR:-/solution}"
if [ ! -f "$SOLUTION_DIR/solve.py" ]; then
  SOLUTION_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
WORKSPACE="${AGENT_WORKSPACE:-/app/environment/workspace}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

AGENT_WORKSPACE="$WORKSPACE" "$PYTHON_BIN" "$SOLUTION_DIR/solve.py"
