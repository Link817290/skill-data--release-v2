#!/usr/bin/env bash
set -euo pipefail
test_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
output="${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}"
mkdir -p "$output"
rm -f -- "$output/reward.txt" "$output/reward_strict.txt" \
  "$output/reward_lenient.txt" "$output/reward.json" "$output/reward_detail.json"
exec python3 -B "$test_dir/validator.py" "${1:-/workspace}" \
  --mode "${LLM_JUDGE_MODE:-${MX6_JUDGE_MODE:-auto}}" \
  --output "$output"
