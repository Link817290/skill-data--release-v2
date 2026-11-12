#!/usr/bin/env bash
set -euo pipefail

SOLUTION_DIR="${SOLUTION_DIR:-/solution}"
if [ ! -d "$SOLUTION_DIR/golden" ]; then
  SOLUTION_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
fi
WORKSPACE="${AGENT_WORKSPACE:-/workspace}"
mkdir -p "$WORKSPACE/output"
cp "$SOLUTION_DIR/golden/hyperkalemia_reasoning_template.docx" "$WORKSPACE/output/"
cp "$SOLUTION_DIR/golden/CASE-001_reasoning.docx" "$WORKSPACE/output/"
cp "$SOLUTION_DIR/golden/CASE-002_reasoning.docx" "$WORKSPACE/output/"
cp "$SOLUTION_DIR/golden/CASE-003_reasoning.docx" "$WORKSPACE/output/"
