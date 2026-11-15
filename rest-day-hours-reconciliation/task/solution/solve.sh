#!/usr/bin/env bash
set -euo pipefail
OUT="${AGENT_WORKSPACE:-/workspace}/output"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE="$(cd "$HERE/../.." && pwd)"
mkdir -p "$OUT"
cp "$PACKAGE/golden/rest-day-review.xlsx" "$OUT/rest-day-review.xlsx"
cp "$PACKAGE/golden/review-conclusions.txt" "$OUT/review-conclusions.txt"
