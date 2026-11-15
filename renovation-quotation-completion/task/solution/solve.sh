#!/bin/bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="${1:-${AGENT_WORKSPACE:-/workspace}}"
mkdir -p "$workspace/output"
golden="$here/../../golden"
if [ ! -d "$golden" ]; then
    golden="${PACKAGE_ROOT:-/package}/golden"
fi
cp "$golden/复桥602计价清单.xlsx" "$workspace/output/"
