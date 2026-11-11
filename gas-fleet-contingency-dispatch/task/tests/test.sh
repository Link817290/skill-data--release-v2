#!/bin/sh
set -eu
# pd-ledger-v1: validator.py takes the deliverable directory (the contract's `validator.py <dir>`)
# This scorer's checks compare float sums at ~1e-6. CPython 3.12 made `sum()` compensated
# (gh-100425), which shifts those sums by an ulp. Prefer an
# interpreter from before that change when the image has one, and fall back to `python3` otherwise
# so an image that ships only 3.12 still runs.
PY_BIN=python3
for c in python3.11 python3.10; do
  if command -v "$c" >/dev/null 2>&1; then PY_BIN="$c"; break; fi
done
LOG_DIR="${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}"
mkdir -p "$LOG_DIR"
# `set -e` would abort the script on a nonzero validator exit, before the artifacts are collected
# and before the reward files are written, and a bare `rc=$?` after the command would then be
# unreachable (it can only ever read 0). Take the status through `|| rc=$?` so a failing validator
# still leaves collected artifacts and an auditable log, and is reported through the exit status.
rc=0
"$PY_BIN" "$(dirname "$0")/validator.py" "${OUTPUT_DIR:-/workspace/output}" > "$LOG_DIR/reward_detail.json" || rc=$?

# Copy deliverables into Harbor's artifact collection directory. Harbor collects
# /logs/artifacts and does not resolve task.toml deliverable paths itself.
ART="${ARTIFACT_OUTPUT_DIR:-/logs/artifacts}"
mkdir -p "$ART" 2>/dev/null || true
cp -r "${OUTPUT_DIR:-/workspace/output}/." "$ART/" 2>/dev/null || true

# --- reward files, taken from the scorer's own detail output ---
python3 - "$LOG_DIR/reward_detail.json" "$LOG_DIR" <<'PY_REWARDS'
import json, pathlib, sys
detail_path, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
try:
    detail = json.loads(detail_path.read_text(encoding="utf-8"))
    rewards = detail["rewards"]
    strict = float(rewards["strict"])
except Exception:
    raise SystemExit(0)
lenient = rewards.get("lenient")
(out / "reward.txt").write_text(f"{strict}\n", encoding="utf-8")
(out / "reward_strict.txt").write_text(f"{strict}\n", encoding="utf-8")
payload = {"reward": strict, "reward_strict": strict}
if lenient is not None:
    (out / "reward_lenient.txt").write_text(f"{lenient}\n", encoding="utf-8")
    payload["reward_lenient"] = lenient
(out / "reward.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY_REWARDS

exit "$rc"
