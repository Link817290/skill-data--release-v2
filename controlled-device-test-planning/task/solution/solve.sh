#!/usr/bin/env bash
set -euo pipefail
WS="${1:-${AGENT_WORKSPACE:-/workspace}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MATERIALS="$WS/materials"
[ -d "$MATERIALS" ] || MATERIALS="$HERE/../environment/workspace/materials"
python3 -B "$HERE/solve.py" "$WS" --materials "$MATERIALS"
