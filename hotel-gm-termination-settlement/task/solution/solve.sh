#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE="${1:-/workspace}"
mkdir -p "$WORKSPACE/output"
cp "$SCRIPT_DIR/reference/赔付清单.xlsx" "$WORKSPACE/output/赔付清单.xlsx"
