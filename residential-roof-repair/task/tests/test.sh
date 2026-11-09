#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python -B tests/entrypoint.py "$@"
