#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-${AGENT_WORKSPACE:-/workspace}}"
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
python3 -B "$HERE/validator.py" "$ROOT/output" --json "$OUT/reward_detail.json"
STATUS=$?
python3 -B - "$OUT" "$STATUS" <<'PY'
import json, math, sys
from pathlib import Path
out = Path(sys.argv[1])
if int(sys.argv[2]):
    (out / "verifier_status.json").write_text('{"verifier_status":"error"}\n', encoding="utf-8")
    raise SystemExit(1)
data = json.loads((out / "reward_detail.json").read_text(encoding="utf-8"))
strict = data["reward_strict"]
lenient = data["reward_lenient"]
assert all(isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1 for value in (strict, lenient))
for name, value in (("reward.txt", strict), ("reward_strict.txt", strict), ("reward_lenient.txt", lenient)):
    (out / name).write_text(f"{value:.9f}\n", encoding="utf-8")
(out / "reward.json").write_text(json.dumps({"reward": strict, "reward_strict": strict, "reward_lenient": lenient}) + "\n", encoding="utf-8")
(out / "verifier_status.json").write_text('{"verifier_status":"ok"}\n', encoding="utf-8")
PY
RESULT=$?
if [ "$RESULT" -eq 0 ]; then
    python3 -B "$HERE/mix_judge/apply.py" --submission-dir "$ROOT/output" --verifier-dir "$OUT" || RESULT=$?
fi
exit "$RESULT"
