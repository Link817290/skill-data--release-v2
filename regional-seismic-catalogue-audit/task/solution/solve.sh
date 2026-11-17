#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/output
printf '{}\n' > /workspace/output/seismic_catalogue_report.json
python3 "$(dirname "$0")/reference_solution.py" /workspace/materials /workspace/output/seismic_catalogue_report.json
