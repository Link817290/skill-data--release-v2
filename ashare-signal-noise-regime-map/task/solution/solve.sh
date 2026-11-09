#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
out=/workspace/regime_map.xlsx
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output) out=$2; shift 2 ;;
    --workspace) out=$2/regime_map.xlsx; shift 2 ;;
    *) out=$1; shift ;;
  esac
done
mkdir -p "$(dirname "$out")"
cp "$here/../../golden/regime_map.xlsx" "$out"
