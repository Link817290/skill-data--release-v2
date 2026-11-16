#!/usr/bin/env bash
set -euo pipefail

answer="${1:-/workspace/output/赔付清单.xlsx}"
out="${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}"
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out" "${LLM_JUDGE_CACHE_DIR:-$out/judge-cache}"
rm -f -- "$out/reward.txt" "$out/reward_strict.txt" \
  "$out/reward_lenient.txt" "$out/reward.json" "$out/scores.json"
printf '%s\n' '{"status":"UNMEASURED","reward":null,"strict":null,"lenient":null}' > "$out/reward_detail.json"

tmp="$out/reward_detail.tmp.json"
rm -f -- "$tmp"
if ! python3 -B "$here/validator.py" "$answer" > "$tmp" 2> "$out/validator.log"; then
  exit 2
fi
python3 - "$tmp" "$out" <<'PY'
import json, pathlib, sys
detail_path, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
detail = json.loads(detail_path.read_text(encoding="utf-8"))
strict = float(detail["rewards"]["strict"])
lenient = float(detail["rewards"]["lenient"])
detail["status"] = "measured"
(out / "reward_detail.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n")
payload = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
payload.update({k: float(v) for k, v in (detail.get("dimension_scores") or {}).items()})
for name in ("reward.json", "scores.json"):
    (out / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
for name, value in (("reward.txt", strict), ("reward_strict.txt", strict), ("reward_lenient.txt", lenient)):
    (out / name).write_text(f"{value:.6f}\n")
PY
rm -f -- "$tmp"
mkdir -p /logs/artifacts
cp "$answer" /logs/artifacts/赔付清单.xlsx 2>/dev/null || true
