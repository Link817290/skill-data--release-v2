#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/output
# Keep a valid recoverable artifact in place before the derivation starts.
printf '{}\n' > /workspace/output/orbit_evidence.json
python3 "$(dirname "$0")/reference_solution.py" /workspace/materials /workspace/output/orbit_evidence.json
