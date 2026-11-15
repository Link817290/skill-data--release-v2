#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT=${1:-/workspace/claim_chart.json}
mkdir -p "$(dirname "$OUT")"
cp "$HERE/../../golden/claim_chart.json" "$OUT"
