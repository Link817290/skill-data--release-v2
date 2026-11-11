#!/usr/bin/env bash
set -euo pipefail

# The reference manuscript is the published revision of the supplied draft. It
# is placed at the deliverable path so the scoring chain can be exercised
# end to end; it is not a derivation of the revision from the draft.
ROOT="${AGENT_WORKSPACE:-${APP_DIR:-/app}/environment}"
mkdir -p "$ROOT/output"
cp "$(dirname "$0")/reference_manuscript.pdf" "$ROOT/output/revised_manuscript.pdf"
