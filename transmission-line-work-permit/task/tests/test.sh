#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACTS="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
MODE="${LLM_JUDGE_MODE:-replay}"
case "$MODE" in
    replay)
        # Routine scoring cannot call a provider, even on a cache miss.
        unset LLM_JUDGE_API_KEY LLM_JUDGE_ENDPOINT
        ;;
    fresh) ;;
    *) printf 'Unsupported LLM_JUDGE_MODE; choose replay or explicitly authorized fresh\n' >&2; exit 2 ;;
esac
mkdir -p "$OUT" "$ARTIFACTS"
# run_verifier.py writes "$OUT/reward.json" with top-level "reward" and strict/lenient fields.
exec "${PYTHON_BIN:-python3}" -B "$HERE/llm_judge/run_verifier.py" \
    "$ROOT" "$OUT" "$ARTIFACTS" --mode "$MODE"
