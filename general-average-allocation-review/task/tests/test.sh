#!/bin/sh
set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ANSWER=${1:-/workspace/deliverables}
OUT=${VERIFIER_OUTPUT_DIR:-/logs/verifier}
ARTIFACTS_OUT=${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}
mkdir -p "$OUT" "$ARTIFACTS_OUT"
find "$OUT" -maxdepth 1 -type f \( -name 'reward.json' -o -name 'reward*.txt' -o -name 'reward_detail.json' \) -delete

python3 "$HERE/validator.py" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log"
status=$?
if [ "$status" -ne 0 ]; then
  find "$OUT" -maxdepth 1 -type f \( -name 'reward.json' -o -name 'reward*.txt' -o -name 'reward_detail.json' \) -delete
  echo "Evaluator could not complete; no score published." >&2
  exit 2
fi

python3 - "$OUT/reward_detail.json" "$OUT" "$ANSWER" "$ARTIFACTS_OUT" <<'PY'
import json
import shutil
import sys
from pathlib import Path

detail_path, out, answer, artifacts = sys.argv[1:]
try:
    detail = json.load(open(detail_path, encoding="utf-8"))
    strict = float(detail["rewards"]["strict"])
    lenient = float(detail["rewards"]["lenient"])
except Exception as exc:
    sys.stderr.write(f"Could not publish verifier rewards: {exc}\n")
    raise SystemExit(2)
for name, value in (("reward.txt", strict), ("reward_strict.txt", strict), ("reward_lenient.txt", lenient)):
    Path(out, name).write_text(f"{value:.6f}\n", encoding="utf-8")
Path(out, "reward.json").write_text(json.dumps({
    "reward": strict,
    "reward_strict": strict,
    "reward_lenient": lenient,
}, indent=2) + "\n", encoding="utf-8")

root = Path(answer) if Path(answer).is_dir() else Path(answer).parent
for name in ("general_average_review.md", "general_average_schedule.csv"):
    source = root / name
    if source.is_file():
        shutil.copy2(source, Path(out, name))
        shutil.copy2(source, Path(artifacts, name))
PY
status=$?
if [ "$status" -ne 0 ]; then
  find "$OUT" -maxdepth 1 -type f \( -name 'reward.json' -o -name 'reward*.txt' -o -name 'reward_detail.json' \) -delete
  exit 2
fi
