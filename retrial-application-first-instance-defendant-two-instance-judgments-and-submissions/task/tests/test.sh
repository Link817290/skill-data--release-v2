#!/usr/bin/env bash
set -uo pipefail
# A required judge/service/schema failure is an infrastructure error, never a candidate zero.
set -eE
abort_scoring() {
  local target="${OUT:-}"
  if [ -n "$target" ]; then
    rm -f "$target"/reward.txt "$target"/reward_strict.txt "$target"/reward_lenient.txt \
      "$target"/reward.json "$target"/reward_detail.json "$target"/verify_result.json \
      "$target"/program_reward_detail.json
  fi
  exit 2
}
trap abort_scoring ERR
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
WS="${1:-/workspace}"
python3 "$(dirname "$0")/validator.py" "$WS" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || abort_scoring
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[2])
try:
    d = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    s = float(d["final_score"])
    # lenient is the binary lens the validator settles, not a second reading of strict.
    lenient = float(d["rewards"]["lenient"])
except Exception as exc:
    sys.stderr.write(f"could not read reward: {exc}\n")
    raise SystemExit(2)
for n in ("reward.txt", "reward_strict.txt"):
    (out / n).write_text(f"{s:.6f}\n", encoding="utf-8")
(out / "reward_lenient.txt").write_text(f"{lenient:.6f}\n", encoding="utf-8")
(out / "reward.json").write_text(
    json.dumps({"reward": s, "reward_strict": s, "reward_lenient": lenient}, indent=2) + "\n",
    encoding="utf-8")
PY
mkdir -p /logs/artifacts
cp "$WS"/artifacts/* /logs/artifacts/ 2>/dev/null || true

exit 0
