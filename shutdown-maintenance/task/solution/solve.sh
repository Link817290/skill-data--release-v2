#!/bin/sh
set -eu
exec python "$(dirname "$0")/solve.py" "$@"
