#!/usr/bin/env bash
set -uo pipefail
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
WS="${1:-/workspace}"
if ! python3 /tests/validator.py "$WS" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  rm -f "$OUT/reward.json" "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt"
  printf '{"status":"UNMEASURED","error":"required source-bound semantic adjudication unavailable or invalid"}\n' > "$OUT/status.json"
  exit 2
fi
# strict = the judge's final_score; lenient = the validator's binary lens over the same ledger
# (positive_earned > 0.50 and at most 2 damage instances), never the strict value copied.
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[2])
try:
    d = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    rewards = d.get("rewards") or {}
    s = float(rewards.get("strict", d["final_score"]))
    l = float(rewards.get("lenient", 0.0))
except Exception as exc:
    sys.stderr.write(f"could not read reward: {exc}\n")
    raise SystemExit(0)
(out / "reward.txt").write_text(f"{s:.6f}\n", encoding="utf-8")
(out / "reward_strict.txt").write_text(f"{s:.6f}\n", encoding="utf-8")
(out / "reward_lenient.txt").write_text(f"{l:.6f}\n", encoding="utf-8")
(out / "reward.json").write_text(
    json.dumps({"reward": s, "reward_strict": s, "reward_lenient": l}, indent=2) + "\n",
    encoding="utf-8")
PY
mkdir -p /logs/artifacts
cp "$WS"/artifacts/* /logs/artifacts/ 2>/dev/null || true

# --- mix judge (installed by mix_judge.py install) ---
# The program judge above has written its verdict. The LLM gate may zero it (gaming,
# or breaking the task text); otherwise it stands. If the LLM cannot be reached the
# program judge's verdict stands. The program judge's own detail is kept beside it.
# Harness conventions only: rewards in $VERIFIER_OUTPUT_DIR, the deliverable root is this
# script's first argument (else $AGENT_WORKSPACE, else /workspace), the gate beside this script.
MJ_OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
MJ_ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
MJ_DIR="$(cd "$(dirname "$0")" && pwd)/mix_judge"
if [ -f "$MJ_DIR/gate_runtime.py" ] && [ -f "$MJ_OUT/reward_detail.json" ]; then
  cp "$MJ_OUT/reward_detail.json" "$MJ_OUT/program_reward_detail.json"
  python3 "$MJ_DIR/gate_runtime.py" score --installed "$MJ_DIR" \
    --deliverable-dir "$MJ_ROOT" --program-detail "$MJ_OUT/program_reward_detail.json" \
    --out "$MJ_OUT" >> "$MJ_OUT/mix_judge.log" 2>&1 || true
fi

exit 0
