"""Decimal calculation helper; the caller establishes eligibility and contract terms."""
from decimal import Decimal,ROUND_HALF_UP
import argparse,json
def number(v):
    if isinstance(v,bool):raise ValueError("Boolean is not a number")
    d=Decimal(str(v))
    if not d.is_finite():raise ValueError("Nonfinite number")
    return d
def cents(v):return number(v).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)
def calculate(data):
    lines=[cents(number(x["quantity"])*number(x["rate"])) for x in data["lines"]]
    earned=sum(lines,Decimal(0))
    opening=number(data["engineering_advance_opening"])
    if opening<0:raise ValueError("Advance opening balance cannot be negative")
    rate=number(data["engineering_recovery_rate"])
    retention_rate=number(data["retention_rate"])
    if not 0<=rate<=1 or not 0<=retention_rate<=1:raise ValueError("Use fractional rates")
    recovery=min(max(cents(earned*rate),Decimal(0)),opening)
    retained=cents(earned*retention_rate)
    added=number(data.get("material_advance_addition",0))
    material_recovery=number(data.get("material_advance_recovery",0))
    other=number(data.get("other_deductions",0))
    return dict(line_amounts=[str(x) for x in lines],earned=str(earned),
                engineering_recovery=str(recovery),retention=str(retained),
                engineering_closing=str(opening-recovery),
                current_net=str(earned+added-recovery-material_recovery-retained-other))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("input");a=p.parse_args()
    with open(a.input,encoding="utf8") as f:data=json.load(f)
    print(json.dumps(calculate(data)))
