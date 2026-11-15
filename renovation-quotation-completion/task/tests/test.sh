#!/bin/bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
deps="$(mktemp -d /tmp/quotation-verifier-deps.XXXXXX)"
trap 'rm -rf "$deps"' EXIT
python3 -m pip install --disable-pip-version-check --no-index --no-deps \
    --find-links="$here/wheels" --target="$deps" -r "$here/requirements.txt" >&2
export PYTHONPATH="$deps${PYTHONPATH:+:$PYTHONPATH}"
python3 -B "$here/validator.py" "${1:-${AGENT_WORKSPACE:-/workspace}}" \
    --result-dir "${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}"
python3 -B "$here/mix_judge/apply.py" \
    --submission-dir "${1:-${AGENT_WORKSPACE:-/workspace}}/output" \
    --verifier-dir "${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}"
python3 - "${VERIFIER_OUTPUT_DIR:-${VERIFIER_LOG_DIR:-/logs/verifier}}/reward.json" <<'PY'
import json
import math
import sys
with open(sys.argv[1], encoding='utf-8') as stream:
    reward = json.load(stream)
assert type(reward['reward']) in (int, float) and math.isfinite(reward['reward'])
assert 0 <= reward['reward'] <= 1
assert reward['reward'] == reward['reward_strict']
assert reward['reward_lenient'] in (0, 1)
PY
