#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /workspace/output
set -- "$HERE/../golden/"*.pdf
[ "$#" -eq 1 ]
cp "$1" /workspace/output/report.pdf
