#!/usr/bin/env python3
"""Aggregate strict and lenient reward files from verifier directories."""
import json, statistics, sys
from pathlib import Path

vals=[]
for p in map(Path, sys.argv[1:]):
    try:
        vals.append(json.loads((p/"reward.json").read_text()))
    except Exception:
        continue
out={"n":len(vals)}
for k in ("reward_strict","reward_lenient"):
    xs=[float(v.get(k,0)) for v in vals]
    out[k]={"mean":statistics.fmean(xs) if xs else 0.0,"min":min(xs) if xs else 0.0,"max":max(xs) if xs else 0.0}
print(json.dumps(out,indent=2))
