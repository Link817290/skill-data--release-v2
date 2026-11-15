#!/usr/bin/env bash
# Routine semantic scoring is replay-only, even if the caller exports fresh mode.
set -euo pipefail
if [ "$#" -gt 1 ]; then
    printf 'Usage: bash tests/score_cached.sh [ARTIFACT_OR_WORKSPACE_DIR]\n' >&2
    exit 2
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LLM_JUDGE_MODE=replay
export LLM_JUDGE_PROTOCOL="${LLM_JUDGE_PROTOCOL:-responses}"
unset LLM_JUDGE_API_KEY LLM_JUDGE_ENDPOINT
exec bash "$HERE/test.sh" "${1:-${AGENT_WORKSPACE:-/workspace}}"
