#!/bin/sh
set -u

TEST_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACTS="${ARTIFACTS_OUT:-/logs/artifacts}"
ANSWER="${1:-/workspace/output/review_report.md}"
if [ -d "$ANSWER" ]; then ANSWER="$ANSWER/output/review_report.md"; fi
mkdir -p "$OUT" "$ARTIFACTS"
rm -f "$OUT/reward.json" "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt"

python3 -B "$TEST_ROOT/validator.py" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"
status=$?
if [ "$status" -ne 0 ]; then exit "$status"; fi

python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, pathlib, sys
detail = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if detail.get("status") != "MEASURED":
    raise SystemExit(2)
out = pathlib.Path(sys.argv[2])
strict = float(detail["reward_strict"]); lenient = float(detail["reward_lenient"])
(out / "reward.txt").write_text(f"{strict:.6f}\n", encoding="utf-8")
(out / "reward_strict.txt").write_text(f"{strict:.6f}\n", encoding="utf-8")
(out / "reward_lenient.txt").write_text(f"{lenient:.6f}\n", encoding="utf-8")
(out / "reward.json").write_text(json.dumps({"reward": strict, "reward_strict": strict,
    "reward_lenient": lenient}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
cp "$ANSWER" "$ARTIFACTS/review_report.md" 2>/dev/null || true
