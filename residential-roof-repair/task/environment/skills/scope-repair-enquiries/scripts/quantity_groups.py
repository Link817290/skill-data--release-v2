"""Summarize normalized scope records without converting unknown quantities to zero.

CSV fields: id,group,unit,quantity,status. Status is included, pending or excluded.
Usage: python quantity_groups.py working.csv --out summary.json
"""
import argparse,csv,json
from decimal import Decimal,InvalidOperation
from pathlib import Path

def normalize_unit(value):
    s=value.strip().lower().replace('²','2').replace('³','3')
    return {'sqm':'m2','sq m':'m2','cum':'m3','cu m':'m3','metre':'m','meter':'m'}.get(s,s)

def summarize(records):
    groups={};seen=set()
    for r in records:
        key=r['id'].strip();status=r['status'].strip().lower()
        if not key or key in seen:raise ValueError('Missing or duplicate record id')
        seen.add(key)
        if status not in {'included','pending','excluded'}:raise ValueError('Unknown scope status')
        if status=='excluded':continue
        group=r['group'].strip();unit=normalize_unit(r['unit'])
        if not group or not unit:raise ValueError('Group and unit are required')
        g=groups.setdefault(group,dict(unit=unit,known=Decimal(0),included_ids=[],pending_ids=[]))
        if g['unit']!=unit:raise ValueError('Incompatible units in group '+group)
        quantity=r['quantity'].strip()
        if status=='pending':
            if quantity:raise ValueError('A pending record must not carry an unconfirmed numeric quantity')
            g['pending_ids'].append(key);continue
        try:value=Decimal(quantity)
        except InvalidOperation as e:raise ValueError('Included quantity is not a number') from e
        if not value.is_finite() or value<0:raise ValueError('Quantity must be finite and nonnegative')
        g['known']+=value;g['included_ids'].append(key)
    return {key:dict(unit=g['unit'],known_total=str(g['known']),complete=not g['pending_ids'],included_ids=sorted(g['included_ids']),pending_ids=sorted(g['pending_ids'])) for key,g in groups.items()}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('csv',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    with a.csv.open(encoding='utf-8-sig',newline='') as f:result=summarize(csv.DictReader(f))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2),encoding='utf8')
if __name__=='__main__':main()
