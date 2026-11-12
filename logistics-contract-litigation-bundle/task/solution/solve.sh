#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
mkdir -p "$ROOT/output"
HERE="$(cd "$(dirname "$0")" && pwd)"
PACKAGE_ROOT="$(cd "$HERE/../.." && pwd)"
find "$PACKAGE_ROOT/golden" -maxdepth 1 -type f -name "*.docx" -exec cp {} "$ROOT/output/" \;
