#!/bin/sh
# Deterministic Oracle: copy the independently authored reference report.
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE="${1:-/workspace}"
mkdir -p "$WORKSPACE/output"
cp "$SCRIPT_DIR/reference_report.md" "$WORKSPACE/output/review_report.md"
printf 'wrote %s\n' "$WORKSPACE/output/review_report.md"
