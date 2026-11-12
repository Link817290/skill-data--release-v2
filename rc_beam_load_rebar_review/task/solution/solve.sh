#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# Workspace resolution, by priority: caller argument, harness variables, the
# conventional mount point, then the copy that ships inside the package.
if [ "${1:-}" != "" ]; then WS=$1
elif [ "${AGENT_WORKSPACE:-}" != "" ]; then WS=$AGENT_WORKSPACE
elif [ "${WORKSPACE_ROOT:-}" != "" ]; then WS=$WORKSPACE_ROOT
elif [ -d /workspace ]; then WS=/workspace
else WS=$HERE/../environment/workspace
fi
# The argument may be the deliverable itself or the workspace root.
case "$WS" in
  *.xlsx) ANSWER=$WS; WS=$(dirname -- "$ANSWER") ;;
  *) ANSWER=$WS/beam_review.xlsx ;;
esac
SOLVER=${SOLUTION_DIR:-/solution}/reference_solution.py
[ -f "$SOLVER" ] || SOLVER=$HERE/reference_solution.py
mkdir -p "$WS"
AGENT_WORKSPACE="$WS" python3 "$SOLVER" "$ANSWER"
# Recalculate formulas when a spreadsheet engine is available; the original
# formulas remain in the workbook for lineage inspection.
if command -v libreoffice >/dev/null 2>&1; then
  TMP=$(mktemp -d)
  libreoffice --headless --convert-to xlsx --outdir "$TMP" "$ANSWER" >/dev/null 2>&1 || true
  if [ -f "$TMP/$(basename "$ANSWER")" ]; then cp "$TMP/$(basename "$ANSWER")" "$ANSWER"; fi
  rm -rf "$TMP"
fi
