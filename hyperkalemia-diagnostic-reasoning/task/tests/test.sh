#!/usr/bin/env bash
set -uo pipefail

ANSWER="${1:-/workspace/output}"
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ANSWER_DIR="$ANSWER"
if [ -f "$ANSWER" ]; then
  ANSWER_DIR="$(dirname -- "$ANSWER")"
elif [ -d "$ANSWER/output" ]; then
  ANSWER_DIR="$ANSWER/output"
fi
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
REVIEW_FILE="${REVIEW_FILE:-$OUT/review.json}"
mkdir -p "$OUT" /logs/artifacts
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward_factual_accuracy.txt"
printf '0\n' > "$OUT/reward_reasoning_quality.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0,"reward_factual_accuracy":0,"reward_reasoning_quality":0}\n' > "$OUT/reward.json"

ARGS=("$ANSWER_DIR")
if [ -f "$REVIEW_FILE" ]; then
  ARGS+=(--review "$REVIEW_FILE")
fi
if ! python3 "$HERE/validator.py" "${ARGS[@]}" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  rm -f "$OUT"/reward*.json "$OUT"/reward*.txt
  exit 2
fi
STATUS="$(python3 - "$OUT/reward_detail.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("status", ""))
PY
)"
if [ "$STATUS" = "REVIEW_REQUIRED" ]; then
  if ! python3 "$HERE/semantic_judge.py" --output "$ANSWER_DIR" --review "$REVIEW_FILE" >> "$OUT/validator.log" 2>&1; then
    rm -f "$OUT"/reward*.json "$OUT"/reward*.txt
    printf '{"status":"judge_infrastructure_error","score_valid":false}\n' > "$OUT/reward_detail.json"
    exit 2
  fi
  if ! python3 "$HERE/validator.py" "$ANSWER_DIR" --review "$REVIEW_FILE" > "$OUT/reward_detail.json" 2>> "$OUT/validator.log"; then
    rm -f "$OUT"/reward*.json "$OUT"/reward*.txt
    exit 2
  fi
fi
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json
import sys

try:
    detail = json.load(open(sys.argv[1], encoding="utf-8"))
    if not detail.get("score_valid"):
        raise ValueError("Evaluator did not produce a valid reviewed score")
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"]["lenient"])
    factual_accuracy = float(detail["rewards"]["factual_accuracy"])
    better_raw = detail["rewards"]["reasoning_quality"]
    reasoning_quality = float(better_raw) if better_raw is not None else 0.0
except Exception as exc:
    sys.stderr.write(f"could not read reward: {exc}\n")
    raise SystemExit(0)

out = sys.argv[2]
open(out + "/reward_strict.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
open(out + "/reward_lenient.txt", "w", encoding="utf-8").write(f"{lenient:.6f}\n")
open(out + "/reward_factual_accuracy.txt", "w", encoding="utf-8").write(f"{factual_accuracy:.6f}\n")
open(out + "/reward_reasoning_quality.txt", "w", encoding="utf-8").write(f"{reasoning_quality:.6f}\n")
open(out + "/reward.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
json.dump(
    {
        "reward": strict,
        "reward_strict": strict,
        "reward_lenient": lenient,
        "reward_factual_accuracy": factual_accuracy,
        "reward_reasoning_quality": reasoning_quality,
    },
    open(out + "/reward.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=2,
)
PY

for name in \
  hyperkalemia_reasoning_template.docx \
  CASE-001_reasoning.docx \
  CASE-002_reasoning.docx \
  CASE-003_reasoning.docx
do
  cp "$ANSWER_DIR/$name" "/logs/artifacts/$name" 2>/dev/null || true
done
exit 0
