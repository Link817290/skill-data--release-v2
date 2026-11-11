#!/usr/bin/env bash
# Unified verifier entry point. Infrastructure failures are UNMEASURED and
# never become a candidate score of zero.
set -uo pipefail
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
WS="${1:-/workspace}"
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! python3 -B "$HERE/validator.py" "$WS" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  printf '{"status":"UNMEASURED","error":"verifier infrastructure failed; see validator.log"}\n' > "$OUT/reward.json"
  rm -f "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt"
  exit 2
fi
python3 -B - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[2])
try:
    d = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    s = float(d["final_score"])
    # lenient is the binary lens the validator settles, not a second reading of strict.
    lenient = float(d["rewards"]["lenient"])
except Exception as exc:
    sys.stderr.write("could not read reward: %s\n" % exc)
    raise SystemExit(2)
for n in ("reward.txt", "reward_strict.txt"):
    (out / n).write_text("%.6f\n" % s, encoding="utf-8")
(out / "reward_lenient.txt").write_text("%.6f\n" % lenient, encoding="utf-8")
(out / "reward.json").write_text(
    json.dumps({"reward": s, "reward_strict": s, "reward_lenient": lenient}, indent=2) + "\n",
    encoding="utf-8")
PY
mkdir -p /logs/artifacts 2>/dev/null || true
cp "$WS"/artifacts/* /logs/artifacts/ 2>/dev/null || true
cp "$WS"/output/*    /logs/artifacts/ 2>/dev/null || true

# Required source-bound semantic review is performed by the validator above.
