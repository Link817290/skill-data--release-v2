#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${1:-${AGENT_WORKSPACE:-/workspace}}"
# T1 oracle: materialize the supplied immutable Golden, not a new derivation.
exec "${PYTHON_BIN:-python3}" -B "$HERE/materialize_golden.py" "$WS"
