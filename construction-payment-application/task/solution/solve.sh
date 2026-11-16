#!/bin/sh
# Replay the accepted authored reference. Oracle assets stay outside the actor image.
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT=/workspace/output
while [ "$#" -gt 0 ]; do
    case "$1" in
        --out) OUT=$2; shift 2 ;;
        --input) shift 2 ;;
        *) OUT=$1; shift ;;
    esac
done
mkdir -p "$OUT"
cp "$HERE/reference/第五期进度付款申报表.xlsx" "$OUT/第五期进度付款申报表.xlsx"
cp "$HERE/reference/第五期进度付款申请函.docx" "$OUT/第五期进度付款申请函.docx"
