#!/bin/bash
set -uo pipefail

OUT="${VERIFIER_OUTPUT_DIR:-/logs/verifier}"
ARTIFACTS=/logs/artifacts
mkdir -p "$OUT" "$ARTIFACTS"
# Seed every reward file before doing anything, so a run that ends without a
# deliverable still leaves a complete, archivable verifier record rather than a
# single stray reward.txt.
printf '0.000000\n' > "$OUT/reward.txt"
printf '0.000000\n' > "$OUT/reward_strict.txt"
printf '0.000000\n' > "$OUT/reward_lenient.txt"
printf '{"reward": 0.0, "reward_strict": 0.0, "reward_lenient": 0.0}\n' > "$OUT/reward.json"
cat > "$OUT/reward_detail.json" <<'SEED'
{"reward": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0}, "reward_formulas": {"strict": "additive published dimensions less unique source-bound deductions; no score caps", "lenient": "independent conjunction of required objectives, acceptance relationships, equipment roles and executable/checkable delivery"}, "errors": ["no deliverable found"]}
SEED
: > "$OUT/validator.log"

ANSWER="${1:-}"
if [ -z "$ANSWER" ]; then
  for candidate in \
    "/workspace/output/LG_OLED65C22LB_HDR_Function_Test_Item_List.xlsx" \
    "/workspace/LG_OLED65C22LB_HDR_Function_Test_Item_List.xlsx" \
    "/app/environment/workspace/LG_OLED65C22LB_HDR_Function_Test_Item_List.xlsx" \
    "/app/environment/output/LG_OLED65C22LB_HDR_Function_Test_Item_List.xlsx" \
    "/workspace/output/LG OLED65C22LB_Hardware_Test_Cases_EN.xlsx" \
    "/workspace/LG OLED65C22LB_Hardware_Test_Cases_EN.xlsx" \
    "/workspace/output/HDR_Function_Test_Item_List.xlsx" \
    "/workspace/HDR_Function_Test_Item_List.xlsx"; do
    if [ -f "$candidate" ]; then ANSWER="$candidate"; break; fi
  done
fi

if [ -z "$ANSWER" ] || [ ! -f "$ANSWER" ]; then
  # The instruction names the deliverable but not a directory, so a submission
  # may land in any of the writable trees. Search all of them before giving up:
  # a workbook that exists but sits one directory over is a delivered workbook.
  ANSWER=$(find /workspace/output /workspace /app/environment/workspace /app/environment/output \
    -maxdepth 2 -type f -iname '*.xlsx' \
    ! -iname 'HDR_Function_Test_Item_List_Template.xlsx' \
    ! -iname 'LG OLED65C22LB_Hardware_Test_Cases_EN.xlsx' \
    2>/dev/null | head -n 1)
fi

if [ -z "$ANSWER" ] || [ ! -f "$ANSWER" ]; then
  echo "No candidate deliverable found" > "$OUT/validator.log"
  exit 0
fi

VALIDATOR=/tests/validator.py
if [ ! -f "$VALIDATOR" ]; then
  VALIDATOR="$(cd "$(dirname "$0")" && pwd)/validator.py"
fi
python3 "$VALIDATOR" "$ANSWER" > "$OUT/reward_detail.json" 2> "$OUT/validator.log" || exit 2
python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, sys
detail_path, output_dir = sys.argv[1:]
try:
    detail = json.load(open(detail_path, encoding="utf-8"))
    reward = float(detail["reward"])
except Exception as exc:
    open(output_dir + "/validator.log", "a", encoding="utf-8").write(f"\nReward parse failure: {exc}\n")
    raise SystemExit(2)
open(output_dir + "/reward.txt", "w", encoding="utf-8").write(f"{reward:.6f}\n")
strict = float(detail.get("rewards", {}).get("strict", reward))
lenient = float(detail.get("rewards", {}).get("lenient", 0.0))
open(output_dir + "/reward_strict.txt", "w", encoding="utf-8").write(f"{strict:.6f}\n")
open(output_dir + "/reward_lenient.txt", "w", encoding="utf-8").write(f"{lenient:.6f}\n")
payload = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient}
for name, points in detail.get("dimension_points", {}).items():
    payload[name] = float(points)
json.dump(payload, open(output_dir + "/reward.json", "w", encoding="utf-8"), indent=2)
PY

suffix="${ANSWER##*.}"
cp "$ANSWER" "$OUT/submission.$suffix" 2>/dev/null || true
cp "$ANSWER" "$ARTIFACTS/$(basename "$ANSWER")" 2>/dev/null || true
exit 0
