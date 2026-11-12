#!/bin/sh
set -eu
artifact_root="${1:-/workspace/output}"
verifier_logs="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$verifier_logs"
command -v libreoffice >/dev/null 2>&1 || {
  echo "LibreOffice is required for native formula recalculation." >&2
  exit 2
}
python3 /tests/validator.py --artifact "$artifact_root/standard_time.xlsx" --logs "$verifier_logs"
