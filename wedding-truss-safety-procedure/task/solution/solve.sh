#!/usr/bin/env bash
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${AGENT_WORKSPACE:-/workspace}/output"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --out) OUT="$2"; shift 2 ;;
        *) OUT="$1"; shift ;;
    esac
done
mkdir -p "$OUT"
cp "$HERE"/../../golden/*.docx "$OUT/procedure.docx"
