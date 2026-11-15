#!/usr/bin/env sh
set -u

OUTPUT_ROOT="${1:-/workspace}"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${SOLUTION_DIR:-}" ] && [ -f "$SOLUTION_DIR/golden_output.xlsx" ]; then
  SOURCE="$SOLUTION_DIR/golden_output.xlsx"
elif [ -f /golden/边坡支护专业分包招标清单.xlsx ]; then
  SOURCE=/golden/边坡支护专业分包招标清单.xlsx
else
  SOURCE="$HERE/golden_output.xlsx"
fi
mkdir -p "$OUTPUT_ROOT"
cp "$SOURCE" "$OUTPUT_ROOT/边坡支护专业分包招标清单.xlsx"
