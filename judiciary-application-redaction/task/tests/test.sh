#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="/logs/verifier"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  LOG_DIR="$SCRIPT_DIR/.verifier"
  mkdir -p "$LOG_DIR"
fi
export VERIFIER_LOG_DIR="$LOG_DIR"
printf '0\n' > "$LOG_DIR/reward_strict.txt"
printf '0\n' > "$LOG_DIR/reward.txt"
printf '0\n' > "$LOG_DIR/reward_lenient.txt"
printf '{"reward":0,"reward_strict":0,"reward_lenient":0}\n' > "$LOG_DIR/reward.json"

OUTPUT="${OUTPUT_PDF:-/workspace/output/sanitized_onboarding_packet.pdf}"
if [[ ! -e "$OUTPUT" ]]; then
  OUTPUT="$SCRIPT_DIR/../environment/workspace/output/sanitized_onboarding_packet.pdf"
fi
# The validator prints one JSON line. Keep only that line so an interpreter or
# library banner on stdout cannot corrupt the report.
# Keep the delivered packet so a later scoring change can be re-applied to the
# existing trials instead of re-running them.
ARTIFACT_DIR="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACT_DIR"
[ -f "$OUTPUT" ] && cp "$OUTPUT" "$ARTIFACT_DIR/sanitized_onboarding_packet.pdf"

REPORT="$(python3 "$SCRIPT_DIR/validator.py" "$OUTPUT" | tail -n 1)"
printf '%s\n' "$REPORT" > "$LOG_DIR/reward_detail.json"
python3 - "$REPORT" <<'PY'
import json
import os
import sys
from pathlib import Path
data = json.loads(sys.argv[1])
rewards = data.get("rewards", {})
strict = float(rewards.get("strict", data.get("reward_strict", 0.0)))
lenient = float(rewards.get("lenient", data.get("reward_lenient", 0.0)))
log_dir = Path(os.environ["VERIFIER_LOG_DIR"])
for name, value in (("reward_strict.txt", strict), ("reward.txt", strict),
                    ("reward_lenient.txt", lenient)):
    with open(log_dir / name, "w", encoding="utf-8") as handle:
        handle.write(f"{value:.6f}\n")
with open(log_dir / "reward.json", "w", encoding="utf-8") as handle:
    json.dump({"reward": strict, "reward_strict": strict, "reward_lenient": lenient}, handle)
    handle.write("\n")
PY
exit 0
