#!/bin/sh
set -eu
root="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
out="${OUTPUT_DIR:-/workspace/output}"
mkdir -p "$out/calculations"
cp "$root/golden/analysis.xlsx" "$out/analysis.xlsx"
cp "$root/golden/decision_report.pdf" "$out/decision_report.pdf"
cp "$root/golden/calculations/README.md" "$root/golden/calculations/domain.py" "$root/golden/calculations/requirements.txt" "$root/golden/calculations/solve.py" "$out/calculations/"
exec "${PYTHON:-python3}" -B "$root/golden/calculations/solve.py" --input "$root/task/environment/workspace/input" --output "$out/calculations"
