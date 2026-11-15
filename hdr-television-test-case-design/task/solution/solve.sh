#!/bin/sh
set -eu

OUT_DIR="${1:-/workspace/output}"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$OUT_DIR"
cp "$HERE/LG OLED65C22LB_Hardware_Test_Cases_EN.xlsx" "$OUT_DIR/LG OLED65C22LB_Hardware_Test_Cases_EN.xlsx"
