"""Audit a long-form resource ledger; does not certify assignment optimality."""
import argparse,csv,json,math
from pathlib import Path

def check(rows,keys,used='used',limit='limit',tolerance=0.0):
    if tolerance<0 or not math.isfinite(tolerance):raise ValueError('Invalid tolerance')
    seen=set();issues=[]
    for index,row in enumerate(rows,2):
        key=tuple(row[k] for k in keys)
        if key in seen:issues.append(dict(row=index,issue='duplicate_key',key=key))
        seen.add(key)
        try:u=float(row[used]);cap=float(row[limit])
        except (ValueError,TypeError):issues.append(dict(row=index,issue='invalid_number',key=key));continue
        if not math.isfinite(u) or not math.isfinite(cap):issues.append(dict(row=index,issue='nonfinite',key=key))
        elif u<0 or cap<0:issues.append(dict(row=index,issue='negative_resource',key=key))
        elif u>cap+tolerance:issues.append(dict(row=index,issue='over_capacity',key=key,used=u,limit=cap))
    return dict(passed=not issues,rows=len(rows),issues=issues)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--keys',nargs='+',required=True);p.add_argument('--used',default='used');p.add_argument('--limit',default='limit');p.add_argument('--tolerance',type=float,default=0);a=p.parse_args()
    with a.input.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    result=check(rows,a.keys,a.used,a.limit,a.tolerance);print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
