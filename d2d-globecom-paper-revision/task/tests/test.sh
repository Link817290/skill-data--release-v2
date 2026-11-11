#!/usr/bin/env sh
set -u

ROOT="${1:-/workspace}"
NAME="revised_manuscript.pdf"
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

VERIFIER_OUT="${VERIFIER_OUT:-/logs/verifier}"
ARTIFACTS_OUT="${ARTIFACTS_OUT:-/logs/artifacts}"
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p "$VERIFIER_OUT" "$ARTIFACTS_OUT"
if [ -f "$ARTIFACT" ]; then
  cp "$ARTIFACT" "$ARTIFACTS_OUT/$NAME"
fi
rm -f "$VERIFIER_OUT/reward.txt" "$VERIFIER_OUT/reward_strict.txt" \
  "$VERIFIER_OUT/reward_lenient.txt" "$VERIFIER_OUT/reward.json" \
  "$VERIFIER_OUT/verify_result.json" "$VERIFIER_OUT/scoring_status.json"

"$PYTHON" -B "$SCRIPT_DIR/validator.py" "$ARTIFACT" > "$VERIFIER_OUT/reward_detail.json" 2> "$VERIFIER_OUT/validator.log"
status=$?
if [ "$status" -ne 0 ]; then
  printf '{"status":"UNMEASURED","infrastructure_error":true,"error":"validator or required semantic judge failed; see validator.log"}\n' > "$VERIFIER_OUT/scoring_status.json"
  exit 2
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
