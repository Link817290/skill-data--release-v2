#!/usr/bin/env bash
# Score one submission with the task-local Program Judge (no model, no network).
# Usage: bash task/tests/test.sh [CANDIDATE_ROOT] [RESULT_JSON]
# CANDIDATE_ROOT (default /workspace) must hold the declared deliverable output/table-consistency-audit.md.
# No other location is accepted (no artifacts/, no workspace-root, no first-non-empty fallback);
# a missing declared deliverable scores 0. Replays of harness-collected rollouts must restage
# artifacts/<file> to output/<file> before calling this script.
# Writes the Program result and the verifier reward files.
set -uo pipefail
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
export SKILL_PACKAGE_ROOT="$TESTS_DIR"
VERIFIER_DIR="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR" 2>/dev/null || VERIFIER_DIR="$(mktemp -d)"
# Zero every reward file first, so a stale or pre-seeded value can never survive a failed run.
printf '0\n' > "$VERIFIER_DIR/reward.txt"
printf '0\n' > "$VERIFIER_DIR/reward_strict.txt"
printf '0\n' > "$VERIFIER_DIR/reward_lenient.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$VERIFIER_DIR/reward.json"
rm -f "$VERIFIER_DIR/reward_detail.json"
CANDIDATE_ROOT="${1:-/workspace}"
# The Program result goes to the verifier directory, never into the agent-writable workspace.
RESULT="${2:-$VERIFIER_DIR/program.json}"
rm -f "$RESULT"
CANDIDATE="$CANDIDATE_ROOT/output/table-consistency-audit.md"
if [ ! -f "$CANDIDATE" ]; then
  echo "declared deliverable output/table-consistency-audit.md not found under $CANDIDATE_ROOT; score 0" > "$VERIFIER_DIR/validator.log"
  printf '{"final_score": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0}, "items": [], "deduction_items": [], "reason": "declared deliverable missing"}\n' > "$RESULT"
  cp "$RESULT" "$VERIFIER_DIR/reward_detail.json" 2>/dev/null || true
  echo 0; exit 0
fi
if ! python3 -B "$TESTS_DIR/program_judge/task_judge.py" "$CANDIDATE" \
    --contract "$TESTS_DIR/rubric-contract.json" --json "$RESULT"; then
  echo "program judge failed; score 0" > "$VERIFIER_DIR/validator.log"
  echo 0; exit 0
fi
python3 -B - "$RESULT" "$VERIFIER_DIR" <<'PY'
import json, sys
from pathlib import Path
program = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
score = program["final_score"]
rewards = program.get("rewards") or {"strict": score, "lenient": None}
lenient = rewards.get("lenient")
# Audit trail: the judge's full result (items, deduction_items, retention, ...) is the ledger.
detail = dict(program)
detail["final_score"] = score
detail["rewards"] = rewards
detail["score"] = score
detail["source"] = "program-judge"
(out / "reward_detail.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(out / "reward.json").write_text(
    json.dumps({"reward": score, "reward_strict": score, "reward_lenient": lenient if lenient is not None else 0}, indent=2) + "\n",
    encoding="utf-8")
(out / "reward.txt").write_text(f"{score}\n", encoding="utf-8")
(out / "reward_strict.txt").write_text(f"{score}\n", encoding="utf-8")
(out / "reward_lenient.txt").write_text(f"{lenient if lenient is not None else 0}\n", encoding="utf-8")
print(score)
PY

# --- mix judge (installed by mix_judge.py install) ---
# The program judge above has written its verdict. The required LLM gate may
# reject it for fabricated coverage or other integrity failures. If that gate
# cannot complete, the evaluator publishes no score. The program detail remains
# beside the gate result for auditability.
# Harness conventions only: rewards in $VERIFIER_OUTPUT_DIR, the deliverable root is this
# script's first argument (else $AGENT_WORKSPACE, else /workspace), the gate beside this script.
MJ_OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
MJ_ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
MJ_DIR="$(cd "$(dirname "$0")" && pwd)/mix_judge"
if [ -f "$MJ_DIR/gate_runtime.py" ] && [ -f "$MJ_OUT/reward_detail.json" ]; then
  cp "$MJ_OUT/reward_detail.json" "$MJ_OUT/program_reward_detail.json"
  if ! python3 "$MJ_DIR/gate_runtime.py" score --installed "$MJ_DIR" \
    --deliverable-dir "$MJ_ROOT" --program-detail "$MJ_OUT/program_reward_detail.json" \
    --out "$MJ_OUT" >> "$MJ_OUT/mix_judge.log" 2>&1; then
    rm -f "$MJ_OUT/reward.json" "$MJ_OUT/reward.txt" \
      "$MJ_OUT/reward_strict.txt" "$MJ_OUT/reward_lenient.txt"
    printf '%s\n' 'Required integrity judge unavailable; no score published.' >&2
    exit 2
  fi
fi
