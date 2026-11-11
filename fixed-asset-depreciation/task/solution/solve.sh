#!/usr/bin/env bash
set -euo pipefail
solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace="${1:-/workspace}"
mkdir -p "$workspace/output"
cp "$solution_dir/reference/fixed_asset_model.xlsx" "$workspace/output/fixed_asset_model.xlsx"
