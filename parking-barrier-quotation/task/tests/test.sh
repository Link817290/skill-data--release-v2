#!/usr/bin/env bash
# Scoring entry point. Missing candidate files score zero; required judge failures publish no score.
set -u
# A required judge/service/schema failure is an infrastructure error, never a candidate zero.
set -eE
abort_scoring() {
  local target="${VERIFIER_OUT:-}"
  if [ -n "$target" ]; then
    rm -f "$target"/reward.txt "$target"/reward_strict.txt "$target"/reward_lenient.txt \
      "$target"/reward.json "$target"/reward_detail.json "$target"/verify_result.json \
      "$target"/program_reward_detail.json
  fi
  exit 2
}
trap abort_scoring ERR

ROOT="${1:-/workspace}"
NAME="quotation.xlsx"
ARTIFACT=""
for candidate in \
  "$ROOT/output/$NAME" \
  "$ROOT/workspace/output/$NAME" \
  "$ROOT/$NAME" \
  "/app/environment/output/$NAME" \
  "/workspace/output/$NAME"; do
  if [ -f "$candidate" ]; then
    ARTIFACT="$candidate"
    break
  fi
done
[ -n "$ARTIFACT" ] || ARTIFACT="$ROOT/output/$NAME"
TARGET="$ARTIFACT"
VERIFIER_OUT="${VERIFIER_OUT:-${VERIFIER_OUTPUT_DIR:-/logs/verifier}}"
ARTIFACTS_OUT="${ARTIFACTS_OUT:-/logs/artifacts}"
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p "$VERIFIER_OUT"
mkdir -p "$ARTIFACTS_OUT"
if [ -f "$ARTIFACT" ]; then
  cp "$ARTIFACT" "$ARTIFACTS_OUT/$NAME"
fi
printf '0.000000\n' > "$VERIFIER_OUT/reward.txt"
printf '0.000000\n' > "$VERIFIER_OUT/reward_strict.txt"
printf '0.000000\n' > "$VERIFIER_OUT/reward_lenient.txt"
printf '{"reward":0.0,"infrastructure_error":true}\n' > "$VERIFIER_OUT/reward.json"
printf '{"reward":0.0,"infrastructure_error":true}\n' > "$VERIFIER_OUT/verify_result.json"

"$PYTHON" -B "$SCRIPT_DIR/validator.py" "$TARGET" > "$VERIFIER_OUT/reward_detail.json" 2> "$VERIFIER_OUT/validator.log"
status=$?
if [ "$status" -ne 0 ]; then
  abort_scoring
fi

"$PYTHON" -B - "$VERIFIER_OUT/reward_detail.json" "$VERIFIER_OUT" <<'PY'
import json
import sys
from pathlib import Path

detail_path = Path(sys.argv[1])
out = Path(sys.argv[2])
detail = json.loads(detail_path.read_text(encoding="utf-8"))
strict = float(detail["rewards"]["strict"])
lenient = float(detail["rewards"]["lenient"])
(out / "reward.txt").write_text(f"{strict:.6f}\n", encoding="utf-8")
(out / "reward_strict.txt").write_text(f"{strict:.6f}\n", encoding="utf-8")
(out / "reward_lenient.txt").write_text(f"{lenient:.6f}\n", encoding="utf-8")
(out / "verify_result.json").write_text(detail_path.read_text(encoding="utf-8"), encoding="utf-8")
compact = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
compact.update(detail.get("group_points", {}))
(out / "reward.json").write_text(json.dumps(compact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
exit 0
