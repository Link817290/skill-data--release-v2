#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${AGENT_WORKSPACE:-/workspace}"
mkdir -p "$WORKSPACE/output"
cp /solution/electrical_drawings.dxf "$WORKSPACE/output/electrical_drawings.dxf"
