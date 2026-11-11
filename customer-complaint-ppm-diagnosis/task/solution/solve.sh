#!/bin/sh
set -eu
solution_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output_path=${1:-/workspace/output}
mkdir -p "$output_path"
cp "$solution_root/../../golden/cppm_diagnosis.xlsx" "$output_path/cppm_diagnosis.xlsx"
