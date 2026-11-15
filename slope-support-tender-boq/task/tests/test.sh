#!/usr/bin/env sh
set -u

ROOT="${1:-/workspace}"
if [ -d "$ROOT/workspace" ]; then
  ARTIFACT="$ROOT/workspace/边坡支护专业分包招标清单.xlsx"
else
  ARTIFACT="$ROOT/边坡支护专业分包招标清单.xlsx"
fi
VERIFIER_OUT="${VERIFIER_OUT:-/logs/verifier}"
ARTIFACTS_OUT="${ARTIFACTS_OUT:-/logs/artifacts}"
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p "$VERIFIER_OUT"
mkdir -p "$ARTIFACTS_OUT"
if [ -f "$ARTIFACT" ]; then
  cp "$ARTIFACT" "$ARTIFACTS_OUT/边坡支护专业分包招标清单.xlsx"
fi
exec "$PYTHON" -B "$SCRIPT_DIR/entrypoint.py" --workbook "$ARTIFACT" --out "$VERIFIER_OUT"
