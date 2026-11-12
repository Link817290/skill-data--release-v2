#!/usr/bin/env bash
# Harbor 评分入口(canonical)。
#   - 判分走 validator.py -> tests/pjroot/ 下的 Program Judge(subprocess 隔离)。
#   - reward 写到 $VERIFIER_OUTPUT_DIR(默认 /logs/verifier),四件齐全:
#     reward.txt / reward_strict.txt / reward_lenient.txt / reward.json。
#   - 缺失交付物可计零；必需 judge 失败删除评分文件并返回 2。
#   - 镜像里保证存在的解释器是 `python3`。
#
# 用法: test.sh [WORKSPACE_OR_ARTIFACT]   默认 /workspace
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
printf '0\n' > "$OUT/reward.txt"
printf '0\n' > "$OUT/reward_strict.txt"
printf '0\n' > "$OUT/reward_lenient.txt"
printf '{"reward": 0, "reward_strict": 0, "reward_lenient": 0}\n' > "$OUT/reward.json"

TARGET="${1:-/workspace}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

python3 -B "$SCRIPT_DIR/validator.py" "$TARGET" --output "$OUT/reward_detail.json" \
  > "$OUT/validator.stdout.log" 2> "$OUT/validator.log" || abort_scoring

python3 - "$OUT/reward_detail.json" "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[2])
try:
    detail = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    strict = float(detail["final_score"])
except Exception as exc:
    sys.stderr.write(f"could not read final_score: {exc}\n")
    raise SystemExit(2)
# lenient is the binary lens the validator settles, not a second reading of strict.
lenient = float(detail["rewards"]["lenient"])
out.joinpath("reward.txt").write_text(f"{strict:.12g}\n", encoding="utf-8")
out.joinpath("reward_strict.txt").write_text(f"{strict:.12g}\n", encoding="utf-8")
out.joinpath("reward_lenient.txt").write_text(f"{lenient:.12g}\n", encoding="utf-8")
out.joinpath("reward.json").write_text(
    json.dumps({"reward": strict, "reward_strict": strict, "reward_lenient": lenient},
               ensure_ascii=False) + "\n", encoding="utf-8")
PY

if [ -d /logs ]; then
  mkdir -p /logs/artifacts 2>/dev/null || true
  cp "$TARGET"/output/* /logs/artifacts/ 2>/dev/null || true
  cp "$TARGET"/artifacts/* /logs/artifacts/ 2>/dev/null || true
fi

exit 0
