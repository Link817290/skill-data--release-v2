#!/bin/sh
set -eu
here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
out="${VERIFIER_OUT:-/logs/verifier}"
submission="${1:-${SUBMISSION_DIR:-/workspace/output}}"
input="${EVALUATION_INPUT:-/workspace/input}"
mode="${LLM_JUDGE_MODE:-fresh}"
case "$mode" in
  fresh) ;;
  replay) SEMANTIC_REPLAY="${SEMANTIC_REPLAY:-$submission/golden_replay/response.json}" ;;
  *) echo "LLM_JUDGE_MODE must be fresh or replay" >&2; exit 2 ;;
esac
mkdir -p "$out"
rm -f "$out/reward.json" "$out/reward.txt" "$out/reward_strict.txt" "$out/reward_lenient.txt" "$out/reward_detail.json" "$out/verify_result.json"
case_dir="$(mktemp -d "$out/evaluation.XXXXXX")"
run="$case_dir/result"
set -- --submission-dir "$submission" --input "$input" --out "$run"
if [ -n "${SEMANTIC_REPLAY:-}" ]; then
  set -- "$@" --semantic-replay "$SEMANTIC_REPLAY"
fi
set +e
python3 -B "$here/evaluate.py" "$@" > "$case_dir/evaluator.log" 2>&1
status=$?
python3 -B "$here/write_reward.py" "$run/result.json" "$out"
published=$?
set -e
if [ "$status" -ne 0 ] || [ "$published" -ne 0 ]; then
  exit 2
fi
