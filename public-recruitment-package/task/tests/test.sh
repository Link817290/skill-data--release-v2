#!/usr/bin/env sh
# Any branch must leave reward files behind: the platform reads them, not stdout.
# Without them a scorer crash and a genuine zero become indistinguishable.
set -u

WORKSPACE="${1:-/workspace}"
VERIFIER_OUTPUT_DIR="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACTS_OUT="${ARTIFACTS_OUT:-/logs/artifacts}"
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p "$VERIFIER_OUTPUT_DIR"
mkdir -p "$ARTIFACTS_OUT"

if [ -d "$WORKSPACE/output" ]; then
  cp "$WORKSPACE/output/"* "$ARTIFACTS_OUT/" 2>/dev/null || true
fi

printf '0.000000\n' > "$VERIFIER_OUTPUT_DIR/reward.txt"
printf '0.000000\n' > "$VERIFIER_OUTPUT_DIR/reward_strict.txt"
printf '0.000000\n' > "$VERIFIER_OUTPUT_DIR/reward_lenient.txt"
printf '{"reward":0.0,"infrastructure_error":true}\n' > "$VERIFIER_OUTPUT_DIR/reward.json"
printf '{"reward":0.0,"infrastructure_error":true}\n' > "$VERIFIER_OUTPUT_DIR/verify_result.json"

# The validator writes reward.json, reward.txt, reward_strict.txt,
# reward_lenient.txt, reward_detail.json, and verify_result.json there.
"$PYTHON" -B "$SCRIPT_DIR/validator.py" "$WORKSPACE" --output-dir "$VERIFIER_OUTPUT_DIR" \
  > /dev/null 2> "$VERIFIER_OUTPUT_DIR/validator.log"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  rm -f "$VERIFIER_OUTPUT_DIR"/reward.txt "$VERIFIER_OUTPUT_DIR"/reward_strict.txt \
    "$VERIFIER_OUTPUT_DIR"/reward_lenient.txt "$VERIFIER_OUTPUT_DIR"/reward.json \
    "$VERIFIER_OUTPUT_DIR"/verify_result.json
  printf '{"status":"unmeasured","measurement_complete":false,"error":"validator or semantic judge failed"}\n' > "$VERIFIER_OUTPUT_DIR/verifier_status.json"
  exit 2
fi
exit 0
