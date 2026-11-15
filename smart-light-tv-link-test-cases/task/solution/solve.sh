#!/usr/bin/env bash
set -euo pipefail
WS="${1:-${AGENT_WORKSPACE:-/workspace}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MATERIALS="$WS/materials"
if [ ! -d "$MATERIALS" ]; then MATERIALS="$HERE/../environment/workspace/materials"; fi
python3 "$HERE/solve.py" "$WS" --materials "$MATERIALS"
