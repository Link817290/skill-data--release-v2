#!/usr/bin/env bash
# Oracle replay: writes the package owner's own delivered quotation, byte for
# byte, as the deliverable. The reference workbook is a real work product and is
# the scoring anchor of RUBRIC.md v3.0; replaying it shows the scorer recognises
# the reference answer (full positive credit on every item).
#
# The copy lives in task/solution/, never in task/environment/, so it is not
# visible to a solver.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${APP_DIR:-/app}/environment"
mkdir -p "$ENV_DIR/output"
cp "$HERE/reference_quotation.xlsx" "$ENV_DIR/output/quotation.xlsx"
echo "wrote $ENV_DIR/output/quotation.xlsx"
