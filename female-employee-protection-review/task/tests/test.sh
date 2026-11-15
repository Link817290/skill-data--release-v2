#!/usr/bin/env bash
set -euo pipefail
TASK_TESTS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="${LLM_JUDGE_MODE:-replay}"
if [[ "$MODE" == auto ]]; then
  if [[ -n "${LLM_JUDGE_BASE_URL:-}" && -n "${LLM_JUDGE_API_KEY:-}" ]]; then MODE=fresh; else MODE=replay; fi
fi
if [[ "$MODE" == replay && ! -d "$TASK_TESTS_DIR/llm_judge/cache" && -n "${LLM_JUDGE_BASE_URL:-}" ]]; then
  MODE=fresh
fi
set -- --mode "$MODE" --cache-dir "${LLM_JUDGE_CACHE_DIR:-/tmp/female-judge-cache}" "$@"
exec python3 "$TASK_TESTS_DIR/validator.py" "$@"
