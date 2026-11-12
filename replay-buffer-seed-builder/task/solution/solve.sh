#!/usr/bin/env sh
# Oracle replay. It copies the reference answer into the deliverable path so the
# harness can prove the scorer reaches full credit on a known-good artifact.
set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
NAME="replay_buffer_seed.jsonl"
SOURCE="$SCRIPT_DIR/reference_$NAME"
[ -f "$SOURCE" ] || SOURCE="/solution/reference_$NAME"

OUT_DIR="${OUTPUT_DIR:-}"
if [ -z "$OUT_DIR" ]; then
  for candidate in /workspace/output /app/environment/output ./output; do
    if [ -d "$(dirname "$candidate")" ]; then
      OUT_DIR="$candidate"
      break
    fi
  done
fi
[ -n "$OUT_DIR" ] || OUT_DIR="./output"

mkdir -p "$OUT_DIR"
cp "$SOURCE" "$OUT_DIR/$NAME"
