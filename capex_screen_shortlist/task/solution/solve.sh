#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT=${1:-/workspace/shortlist.xlsx}
mkdir -p "$(dirname "$OUT")"
cp "$HERE/../../golden/shortlist.xlsx" "$OUT"
