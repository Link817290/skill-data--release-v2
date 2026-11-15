#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
set -- --artifact "${1:-/workspace/output}" --output "${VERIFIER_OUTPUT_DIR:-/logs/verifier}" --mode "${LLM_JUDGE_MODE:-replay}"
if [ -n "${GODOT_TRUSTED_BUNDLE:-}" ]; then set -- "$@" --bundle "$GODOT_TRUSTED_BUNDLE"; fi
if [ -n "${GODOT_TRUSTED_EVIDENCE:-}" ]; then set -- "$@" --evidence "$GODOT_TRUSTED_EVIDENCE"; fi
if [ -n "${LLM_JUDGE_CACHE_DIR:-}" ]; then set -- "$@" --cache-dir "$LLM_JUDGE_CACHE_DIR"; fi
python3 "$HERE/calibration/verify.py" "$@"
