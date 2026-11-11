#!/bin/sh
set -eu
tests_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -B "$tests_root/entrypoint.py" "$@"
