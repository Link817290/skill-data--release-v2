#!/usr/bin/env bash
# harbor 归一化封装：跑 validator.py 抽 final_score，写数值 reward.json 到 /logs/verifier。
set -euo pipefail
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
mkdir -p "$OUT"
# Zero every reward file before scoring, so a crash can never leave a stale or pre-seeded score.
for n in reward.txt reward_strict.txt reward_lenient.txt; do printf '0\n' > "$OUT/$n"; done
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
WS="${1:-/workspace}"
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
if ! python3 -B "$TESTS_DIR/validator.py" "$WS" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"; then
  printf '{"status":"UNMEASURED","error":"verifier infrastructure failed; see validator.log"}\n' > "$OUT/status.json"
  exit 1
fi
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[2])
try:
    d = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    s = float(d["final_score"])
except Exception as exc:
    sys.stderr.write(f"could not read reward: {exc}\n")
    raise SystemExit(1)
for n in ("reward.txt", "reward_strict.txt", "reward_lenient.txt"):
    (out / n).write_text(f"{s:.6f}\n", encoding="utf-8")
(out / "reward.json").write_text(
    json.dumps({"reward": s, "reward_strict": s, "reward_lenient": s}, indent=2) + "\n",
    encoding="utf-8")
PY
mkdir -p "$OUT/artifacts"
cp "$WS"/artifacts/*.md "$OUT/artifacts/" 2>/dev/null || true

# --- reward_lenient, taken from the scorer's own detail output ---
python3 - "${OUT}/reward_detail.json" "${OUT}" <<'PY_LENIENT'
import json, pathlib, sys
detail_path, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
try:
    detail = json.loads(detail_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
rewards = detail.get("rewards")
lenient = rewards.get("lenient") if isinstance(rewards, dict) else None
if lenient is None:
    raise SystemExit(0)
(out / "reward_lenient.txt").write_text(f"{lenient}\n", encoding="utf-8")
reward_json = out / "reward.json"
try:
    payload = json.loads(reward_json.read_text(encoding="utf-8"))
except Exception:
    payload = {}
payload["reward_lenient"] = lenient
reward_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY_LENIENT

exit 0
