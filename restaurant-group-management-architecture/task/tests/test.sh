#!/usr/bin/env bash
# Score one submission with targeted source-bound semantic adjudication.
# Usage: bash tests/test.sh [WORKSPACE_ROOT]
# Only the declared deliverable WORKSPACE_ROOT/output/control-system-and-long-term-architecture.md is
# scored (fix batch 1, C-VER-014): no fallback to artifacts/, the workspace root or a bare file name;
# a missing declared file scores 0. The Program result and the verifier reward files are written to
# $VERIFIER_OUTPUT_DIR (default /logs/verifier); nothing is written to or read back from the workspace.
set -uo pipefail
# A required judge/service/schema failure is an infrastructure error, never a candidate zero.
set -eE
abort_scoring() {
  local target="${VERIFIER_DIR:-}"
  if [ -n "$target" ]; then
    rm -f "$target"/reward.txt "$target"/reward_strict.txt "$target"/reward_lenient.txt \
      "$target"/reward.json "$target"/reward_detail.json "$target"/verify_result.json \
      "$target"/program_reward_detail.json
  fi
  exit 2
}
trap abort_scoring ERR
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
export SKILL_PACKAGE_ROOT="$TESTS_DIR"
VERIFIER_DIR="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR" 2>/dev/null || VERIFIER_DIR="$(mktemp -d)"
# Every reward file starts at 0, so a stale or pre-seeded reward_strict.txt / reward_lenient.txt can
# never survive a run that produces no score (B4).
for n in reward.txt reward_strict.txt reward_lenient.txt; do printf '0\n' > "$VERIFIER_DIR/$n"; done
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$VERIFIER_DIR/reward.json"
CANDIDATE_ROOT="${1:-/workspace}"
CANDIDATE="$CANDIDATE_ROOT/output/control-system-and-long-term-architecture.md"
if [ ! -s "$CANDIDATE" ]; then
  echo "declared deliverable output/control-system-and-long-term-architecture.md not found" > "$VERIFIER_DIR/validator.log"
  echo 0; exit 0
fi
# The Program result lives in a private temporary file (never the agent-writable workspace) and is
# removed before the judge runs, so only this run's result can be read.
RESULT="$(mktemp "${TMPDIR:-/tmp}/program.XXXXXX.json")"
rm -f "$RESULT"
trap 'rm -f "$RESULT"' EXIT
if ! python3 -B "$TESTS_DIR/program_judge/task_judge.py" "$CANDIDATE" \
     --contract "$TESTS_DIR/rubric-contract.json" --json "$RESULT" 2> "$VERIFIER_DIR/validator.log" \
   || [ ! -s "$RESULT" ]; then
  echo "SCORING ERROR: judge produced no result for $CANDIDATE" >> "$VERIFIER_DIR/validator.log"
  abort_scoring
fi
python3 -B - "$RESULT" "$VERIFIER_DIR" <<'PY'
import json, sys
from pathlib import Path
program = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
score, version = program["final_score"], program.get("rubric_version")
rewards = program.get("rewards") or {"strict": score, "lenient": None}
lenient = rewards.get("lenient")
(out / "reward.json").write_text(
    json.dumps({"reward": score, "reward_strict": score, "reward_lenient": lenient}, indent=2) + "\n",
    encoding="utf-8")
# Full Program result (items, deduction_items, penalty_instances, retention_multiplier ...) is the
# audit trail (C-VER-010); score / rewards / source stay at the top level as before.
detail = {**program, "score": score, "rewards": rewards, "rubric_version": version, "source": "program-judge"}
(out / "reward_detail.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(out / "reward.txt").write_text(f"{score}\n", encoding="utf-8")
(out / "reward_strict.txt").write_text(f"{score}\n", encoding="utf-8")
if lenient is not None:
    (out / "reward_lenient.txt").write_text(f"{lenient}\n", encoding="utf-8")
print(score)
PY

exit 0
