#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$HERE/test_native.sh" "$@"
python3 "$HERE/normalize_reward.py" "${VERIFIER_OUTPUT_DIR:-/logs/verifier}/reward.json"
