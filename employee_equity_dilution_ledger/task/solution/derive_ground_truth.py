#!/usr/bin/env python3
"""Derive verifier facts from a source-derived reference workbook."""
import json, sys
from openpyxl import load_workbook

if len(sys.argv) != 3:
    raise SystemExit("usage: derive_ground_truth.py <golden.xlsx> <ground_truth.json>")
wb=load_workbook(sys.argv[1],data_only=True)

def lookup(sheet,label,col):
    ws=wb[sheet]
    for row in ws.iter_rows(values_only=True):
        if str(row[0] or "").strip().lower()==label.lower(): return row[col]
    raise RuntimeError(f"missing {sheet}:{label}")

inputs={
 "authorized_pool":lookup("Inputs","Authorized pool",1),
 "available_pool":lookup("Inputs","Available for future awards",1),
 "basic_shares":lookup("Inputs","Basic weighted-average shares",1),
 "closing_price":lookup("Inputs","Closing price",1),
 "psu_max_factor":lookup("Inputs","PSU maximum factor",1),
 "option_pool_multiplier":lookup("Inputs","Option pool multiplier",1),
 "full_value_pool_multiplier":lookup("Inputs","Full-value pool multiplier",1),
 "aggregate_options_exercised":lookup("Inputs","Aggregate options exercised",1),
 "aggregate_cash":lookup("Inputs","Aggregate option cash proceeds",1),
 "aggregate_intrinsic":lookup("Inputs","Aggregate option intrinsic value",1),
 "maximum_outstanding_securities":lookup("Inputs","Maximum outstanding securities (plan table)",1),
}
awards={}
for key,label in [("options","Options"),("rsus","RSUs"),("psus","PSUs")]:
 vals=next(r for r in wb["Award_Ledger"].iter_rows(values_only=True) if str(r[0] or "").lower()==label.lower())
 awards[key]=dict(zip(["beginning","grants","exercises","forfeitures","expirations","ending","price"],vals[1:8]))
exercise={name:lookup("Exercise_Ledger",name,1) for name in ["Jeffrey Niew","John Anderson","Raymond Cabrera","Daniel Giesecke","Robert Perna"]}
exercise.update({"named_subtotal":lookup("Exercise_Ledger","Named-person subtotal",1),"residual":lookup("Exercise_Ledger","Other employees / unassigned aggregate",1),"aggregate":lookup("Exercise_Ledger","Annual-report aggregate",1)})
summary={
 "option_incremental":lookup("Dilution_Summary","Option incremental shares (treasury-stock)",1),
 "rsu_potential":lookup("Dilution_Summary","Unvested RSUs",1),
 "psu_target":lookup("Dilution_Summary","Unvested PSUs at target",1),
 "psu_maximum":lookup("Dilution_Summary","Unvested PSUs at target",2),
 "total_potential_base":lookup("Dilution_Summary","Total potential award shares",1),
 "total_potential_maximum":lookup("Dilution_Summary","Total potential award shares",2),
 "tsm_incremental_base":lookup("Dilution_Summary","TSM diluted incremental shares",1),
 "tsm_incremental_maximum":lookup("Dilution_Summary","TSM diluted incremental shares",2),
 "denominator":lookup("Dilution_Summary","Basic weighted-average denominator",1),
 "dilution_base":lookup("Dilution_Summary","Potential dilution %",1),
 "dilution_maximum":lookup("Dilution_Summary","Potential dilution %",2),
 "grant_pool_charge_base":lookup("Dilution_Summary","2024 grant pool charge",1),
 "grant_pool_charge_maximum":lookup("Dilution_Summary","2024 grant pool charge",2),
 "available_pool":lookup("Dilution_Summary","Available future pool",1),
}
open(sys.argv[2],"w",encoding="utf-8").write(json.dumps({"inputs":inputs,"awards":awards,"exercise":exercise,"summary":summary},indent=2)+"\n")
