#!/bin/sh
# Always initialize every scalar so an empty workspace remains an observed zero.
set -u
ANSWER="${1:-/workspace/output/揚州慢.mei}"
if [ -d "$ANSWER" ]; then
  if [ "$(basename "$ANSWER")" = "output" ]; then
    ANSWER="$ANSWER/揚州慢.mei"
  else
    ANSWER="$ANSWER/output/揚州慢.mei"
  fi
fi
OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACT_OUT="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
WORKSPACE="${AGENT_WORKSPACE:-/workspace}"
VALIDATOR="$(dirname "$0")/validator.py"
[ -f "$VALIDATOR" ] || VALIDATOR=/tests/validator.py
mkdir -p "$OUT"
mkdir -p "$ARTIFACT_OUT" 2>/dev/null || true

printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '0\n' > "$OUT/reward.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"

if [ -f "$ANSWER" ]; then
  python3 "$VALIDATOR" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || true
  python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys
detail_path, output_dir = sys.argv[1:]
try:
    detail = json.load(open(detail_path, encoding="utf-8"))
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"]["lenient"])
except Exception as exc:
    open(output_dir + "/validator.log", "a", encoding="utf-8").write(f"could not read validator result: {exc}\n")
    raise SystemExit(0)
open(output_dir + "/reward_strict.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
open(output_dir + "/reward_lenient.txt", "w", encoding="utf-8").write(f"{lenient:.6f}\n")
open(output_dir + "/reward.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
payload = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
payload.update({key: float(value) for key, value in detail.get("group_points", {}).items()})
json.dump(payload, open(output_dir + "/reward.json", "w", encoding="utf-8"), indent=2)
PY
else
  printf 'MEI deliverable is missing: %s\n' "$ANSWER" > "$OUT/validator.log"
fi

cp "$ANSWER" "$OUT/揚州慢.mei" 2>/dev/null || true
cp "$ANSWER" "$ARTIFACT_OUT/揚州慢.mei" 2>/dev/null || true
tar czf "$OUT/workspace_snapshot.tar.gz" -C "$WORKSPACE" . 2>/dev/null || true
exit 0
