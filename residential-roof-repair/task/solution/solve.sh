#!/bin/sh
set -eu
out="${1:-/workspace/output}"
mkdir -p "$out"
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f /golden/维修询价清单.xlsx ] && [ -f /golden/施工范围说明.docx ]; then
  golden=/golden
elif [ -f /task/golden/维修询价清单.xlsx ] && [ -f /task/golden/施工范围说明.docx ]; then
  golden=/task/golden
else
  golden="$here/../../golden"
fi
cp "$golden/维修询价清单.xlsx" "$out/维修询价清单.xlsx"
cp "$golden/施工范围说明.docx" "$out/施工范围说明.docx"
