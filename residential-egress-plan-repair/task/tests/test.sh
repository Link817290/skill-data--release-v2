#!/usr/bin/env bash
set -uo pipefail

SUBMISSION="${1:-/workspace/output}"
if [[ -f "$SUBMISSION" ]]; then SUBMISSION="$(dirname "$SUBMISSION")"; fi
if [[ -d "$SUBMISSION/output" ]]; then SUBMISSION="$SUBMISSION/output"; fi
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACT_OUT="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$OUT" "$ARTIFACT_OUT"
printf '0\n' > "$OUT/reward.txt"
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
python3 "$(dirname "$0")/validator.py" "$SUBMISSION" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || true
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json
import sys
detail_path, out = sys.argv[1:]
try:
    detail = json.load(open(detail_path, encoding="utf-8"))
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"].get("lenient", 0.0))
except Exception:
    strict = 0.0
    lenient = 0.0
for name in ("reward.txt", "reward_strict.txt"):
    with open(out + "/" + name, "w", encoding="utf-8") as stream:
        stream.write(f"{strict:.6f}\n")
with open(out + "/reward_lenient.txt", "w", encoding="utf-8") as stream:
    stream.write(f"{lenient:.6f}\n")
with open(out + "/reward.json", "w", encoding="utf-8") as stream:
    json.dump({"reward": strict, "reward_strict": strict, "reward_lenient": lenient}, stream, indent=2)
PY
for artifact in inspection_report.json layer_inventory.json extracted_original_layout.json violations_before.json repaired_layout.json changes.json repair_memo.md repaired_plan.dxf; do
  [[ -f "$SUBMISSION/$artifact" ]] && cp "$SUBMISSION/$artifact" "$ARTIFACT_OUT/$artifact" 2>/dev/null || true
done
# Archive the workspace snapshot beside the verifier result for offline review.
# Harbor collects /logs/artifacts before this stage, so the snapshot belongs in /logs/verifier.
_ARCH="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$_ARCH" 2>/dev/null || true
tar czf "$_ARCH/workspace_snapshot.tar.gz" -C "${AGENT_WORKSPACE:-/workspace}" . 2>/dev/null || true

# --- mix judge (installed by mix_judge.py install) ---
# The program judge above has written its verdict. The required LLM gate may zero it
# for gaming or a substantive task-text violation. Judge infrastructure failure leaves
# the result unmeasured. The program judge's own detail is kept beside the mixed result.
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
    python3 - "$MJ_OUT" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
for name in ("reward.json", "reward.txt", "reward_strict.txt", "reward_lenient.txt"):
    (out / name).unlink(missing_ok=True)
(out / "verifier_status.json").write_text(json.dumps({
    "status": "unmeasured",
    "measurement_complete": False,
    "error": "required LLM judge failed; see mix_judge.log"
}, indent=2) + "\n", encoding="utf-8")
PY
    exit 2
  fi
fi

exit 0
