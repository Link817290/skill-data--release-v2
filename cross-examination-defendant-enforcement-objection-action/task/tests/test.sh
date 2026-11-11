#!/usr/bin/env bash
set -uo pipefail
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
WS="${1:-/workspace}"
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! python3 -B "$HERE/validator.py" "$WS" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
    rm -f "$OUT/reward.json" "$OUT/reward.txt" "$OUT/reward_strict.txt" "$OUT/reward_lenient.txt"
    printf '{"status":"UNMEASURED","error":"required semantic adjudication unavailable or invalid"}\n' > "$OUT/status.json"
    exit 2
fi
# strict = the judge's final_score; lenient = the contract's named legal-usability gate,
# never an aggregate-score threshold or the strict value copied.
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
    raise SystemExit(2)
(out / "reward.txt").write_text(f"{s:.6f}\n", encoding="utf-8")
(out / "reward_strict.txt").write_text(f"{s:.6f}\n", encoding="utf-8")
(out / "reward_lenient.txt").write_text(f"{l:.6f}\n", encoding="utf-8")
(out / "reward.json").write_text(
    json.dumps({"reward": s, "reward_strict": s, "reward_lenient": l}, indent=2) + "\n",
    encoding="utf-8")
PY
ARTIFACT_OUT="${VERIFIER_ARTIFACT_DIR:-$(dirname "$OUT")/artifacts}"
mkdir -p "$ARTIFACT_OUT"
if [ -d "$WS/artifacts" ]; then
    cp "$WS"/artifacts/* "$ARTIFACT_OUT"/ 2>/dev/null || true
fi


exit 0
