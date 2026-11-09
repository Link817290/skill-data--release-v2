#!/bin/sh
set -eu
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
output="${OUTPUT_DIR:-/workspace/output}"
mkdir -p "$output/measurement-check"
cp "$here/measurement_check.py" "$output/measurement-check/measurement_check.py"
cp "$here/README.md" "$output/measurement-check/README.md"
cp "$here/requirements.txt" "$output/measurement-check/requirements.txt"
if [ "$#" -eq 0 ]; then
  set -- --mass /workspace/input/instrument-history/mass-checks.csv \
    --optical /workspace/input/instrument-history/optical-checks.csv \
    --config /workspace/input/instrument-history/control-settings.json \
    --output "$output"
fi
exec python "$output/measurement-check/measurement_check.py" "$@"
