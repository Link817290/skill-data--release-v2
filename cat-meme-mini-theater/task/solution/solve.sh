#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${AGENT_WORKSPACE:-/workspace}/output"
mkdir -p "$OUT"
# The Oracle is an explicit authored reference fixture, not independent generation.
tar -xzf "$HERE/reference.tar.gz" -C "$OUT"
printf 'Oracle fixture materialized. Skills present: '
if [ -d /skills/cat-meme-stagecraft ]; then printf 'yes\n'; else printf 'no\n'; fi
