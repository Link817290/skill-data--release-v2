#!/usr/bin/env bash
set -uo pipefail

SUBMISSION="${1:-/workspace/output/citation_audit.json}"
if [[ -d "$SUBMISSION" && -f "$SUBMISSION/output/citation_audit.json" ]]; then
  SUBMISSION="$SUBMISSION/output/citation_audit.json"
fi

OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACT_OUT="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$OUT" "$ARTIFACT_OUT"
# Zero every reward file first, so a stale or pre-seeded value can never survive a failed run.
printf '0\n' > "$OUT/reward.txt"
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$OUT/reward.json"
rm -f "$OUT/reward_detail.json"

VALIDATOR_PATH="${VALIDATOR_PATH:-$(dirname "$0")/validator.py}"
python3 "$VALIDATOR_PATH" "$SUBMISSION" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || true

python3 - "$OUT/reward_detail.json" "$OUT" "$ARTIFACT_OUT" "$SUBMISSION" <<'PY'
import json
import shutil
import sys
import os
detail_path, out, artifact_out, submission = sys.argv[1:]
try:
    detail = json.load(open(detail_path, encoding="utf-8"))
    strict = float(detail["rewards"]["strict"])
except Exception:
    strict = 0.0
for name in ("reward.txt", "reward_strict.txt"):
    with open(out + "/" + name, "w", encoding="utf-8") as stream:
        stream.write(f"{strict:.6f}\n")
with open(out + "/reward.json", "w", encoding="utf-8") as stream:
    json.dump({"reward": strict, "reward_strict": strict}, stream, indent=2)
try:
    src = submission
    if os.path.isdir(src):
        src = os.path.join(src, 'output/citation_audit.json')
    shutil.copy2(src, os.path.join(artifact_out, 'citation_audit.json'))
except Exception:
    pass
PY

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
