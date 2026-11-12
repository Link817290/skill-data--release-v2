#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/output
python3 "$(dirname "$0")/reference_solution.py" /workspace /workspace/output/citation_audit.json
