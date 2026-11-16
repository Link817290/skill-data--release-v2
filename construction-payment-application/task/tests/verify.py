"""Derive payment checks from public materials; accept equivalent row ordering."""
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
import argparse,json,re
from openpyxl import load_workbook
from docx import Document

class Unmeasured(Exception):pass
def dec(v):
    if isinstance(v,bool):raise ValueError("Boolean is not a financial value")
    d=Decimal(str(v))
    if not d.is_finite():raise ValueError("Nonfinite value")
    return d
def money(v):return dec(v).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)
def norm(v):return re.sub(r"\s+","",str(v if v is not None else ""))
def records(sheet,required):
    for row in sheet:
        labels=[norm(c.value) for c in row]
        if all(norm(h) in labels for h in required):
            indexes={h:labels.index(norm(h)) for h in required};result=[]
            for values in sheet.iter_rows(min_row=row[0].row+1,values_only=True):
                if any(v is not None for v in values):
                    result.append({k:values[i] if i<len(values) else None for k,i in indexes.items()})
            return result
    raise ValueError("Missing required fields in "+sheet.title)
def source(input_dir):
    doc=Document(input_dir/"合同条款及报送联系单.docx")
    text="\n".join(p.text for p in doc.paragraphs)
    alltext=text+"\n"+"\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    cutoff_match=re.search(r"签认资料截止时间为(\d+)月(\d+)日",text)
    if not cutoff_match:raise ValueError("Document cutoff unavailable")
    cutoff=f"2019-{int(cutoff_match[1]):02d}-{int(cutoff_match[2]):02d}"
    clauses={r.cells[0].text:r.cells[1].text for t in doc.tables for r in t.rows[1:]}
    rates={k:dec(re.search(r"(\d+(?:\.\d+)?)%",clauses[k])[1])/100 for k in ["保留金","工程预付款","材料预付款"]}
    w=load_workbook(input_dir/"第五期计量签认资料.xlsx",data_only=True)
    prices={}
    for row in records(w["单价清单"],["编码","项目名称","单位","单价（元）","价格依据","确认日期","价格状态"]):
        prices[norm(row["编码"])]=row
    measurements=records(w["工程计量"],["单据号","编码","上期末累计量","本期末累计量","签认日期","记录状态"])
    lines={};pending={}
    def insert(code,q,date,state,ref):
        if code in lines or code in pending:raise ValueError("Ambiguous active measurement "+code)
        rate=prices[code]
        eligible=bool(date) and str(date)<=cutoff and state=="已签认" and bool(rate["确认日期"]) and str(rate["确认日期"])<=cutoff and "申报价" not in str(rate["价格状态"])
        row=dict(quantity=q,rate=dec(rate["单价（元）"]),ref=ref,name=rate["项目名称"],unit=rate["单位"])
        row["category"]="变更项目" if code.startswith("V") else "计日工项目" if code.startswith("D") else "合同单价项目"
        row["amount"]=money(q*row["rate"])
        (lines if eligible else pending)[code]=row
    for row in measurements:
        if "替代" in str(row["记录状态"]):continue
        insert(norm(row["编码"]),dec(row["本期末累计量"])-dec(row["上期末累计量"]),row["签认日期"],row["记录状态"],row["单据号"])
    for row in records(w["计日工"],["单据号","编码","台时","现场确认日期","记录状态"]):
        insert(norm(row["编码"]),dec(row["台时"]),row["现场确认日期"],row["记录状态"],row["单据号"])
    funds=load_workbook(input_dir/"资金往来及代扣资料.xlsx",data_only=True)
    opening={norm(r["项目"]):dec(r["累计金额（元）"]) for r in records(funds["期初结转"],["项目","累计金额（元）"]) if r["累计金额（元）"] is not None}
    materials=records(funds["材料收发"],["凭据","数量","原计付/确认单价","比例","业务记录"])
    material_new=Decimal(0);material_recovery=Decimal(0)
    for row in materials:
        proportion=dec(str(row["比例"]).replace("%",""))/100
        amount=money(dec(row["数量"])*dec(row["原计付/确认单价"])*proportion)
        if "核销" in str(row["业务记录"]):material_recovery+=amount
        elif "批准计付" in str(row["业务记录"]):material_new+=amount
        else:raise ValueError("Unclassified material advance")
    other=sum(dec(r["金额（元）"]) for r in records(funds["代扣凭据"],["凭据编号","金额（元）"]) if r["金额（元）"] is not None)
    return dict(lines=lines,pending=pending,rates=rates,opening=opening,material_new=material_new,material_recovery=material_recovery,other=other,cutoff=cutoff)
def verify(submission,input_dir):
    ref=source(input_dir)
    p=submission/"第五期进度付款申报表.xlsx";d=submission/"第五期进度付款申请函.docx"
    if not p.is_file() or not d.is_file():return dict(measurement_complete=True,passed=False,score=0,reason="Missing required output")
    try:
        w=load_workbook(p,data_only=True);formula=load_workbook(p,data_only=False)
        uncached_formulas=[]
        for s in formula:
            for row in s:
                for c in row:
                    if c.data_type=="f" and w[s.title][c.coordinate].value is None:
                        uncached_formulas.append(f"{s.title}!{c.coordinate}")
        line_rows=records(w["计价明细"],["编码","本期申报量","适用单价","本期价款","费用类别"])
        categories=["合同单价项目","变更项目","计日工项目"]
        lines={};duplicate=False
        for row in line_rows:
            key=norm(row["编码"])
            # Supporting and pending schedules may follow the claim table on the
            # same worksheet.  Only rows explicitly assigned to a payable work
            # category are submitted claim lines.
            if not key or norm(row["费用类别"]) not in categories:continue
            if key in lines:duplicate=True
            lines[key]=row
        summaries=records(w["支付汇总"],["项目","上期末累计","本期申请","本期末累计"])
        totals={}
        for row in summaries:
            key=norm(row["项目"])
            if key:totals.setdefault(key,[]).append(row)
        calcs=records(w["扣款计算"],["计算项目","金额（元）"])
        balances={}
        for row in calcs:
            key=norm(row["计算项目"])
            if not key:continue
            balances.setdefault(key,[]).append(row["金额（元）"])
        letter_doc=Document(d)
        letter="\n".join(p.text for p in letter_doc.paragraphs)+"\n"+"\n".join(c.text for t in letter_doc.tables for r in t.rows for c in r.cells)
        checks={k:[] for k in ["eligible_lines","line_arithmetic","current_rollup","advances","retention_other","cumulative","summary_arithmetic","letter_and_balances"]}
        checks["eligible_lines"].append(set(lines)==set(ref["lines"]) and not duplicate)
        def value(raw):
            try:return dec(raw)
            except Exception:return None
        def equal(raw,want):
            got=value(raw)
            return got is not None and got==want
        def submitted(category,column):
            rows=totals.get(category,[])
            values=[value(row.get(column)) for row in rows]
            if not values or any(v is None for v in values) or any(v!=values[0] for v in values[1:]):return None
            return values[0]
        def balance(item):
            values=[value(v) for v in balances.get(item,[])]
            if not values or any(v is None for v in values) or any(v!=values[0] for v in values[1:]):return None
            return values[0]
        for code,want in ref["lines"].items():
            row=lines.get(code)
            checks["eligible_lines"].append(row is not None and equal(row["本期申报量"],want["quantity"]) and equal(row["适用单价"],want["rate"]) and norm(row["费用类别"])==want["category"])
        rolled={k:Decimal(0) for k in categories}
        rollup_valid={k:True for k in categories}
        for row in lines.values():
            a=value(row["本期价款"]);q=value(row["本期申报量"]);r=value(row["适用单价"])
            checks["line_arithmetic"].append(a is not None and q is not None and r is not None and a==money(q*r))
            cat=norm(row["费用类别"])
            if a is None:rollup_valid[cat]=False
            else:rolled[cat]+=a
        earned=sum(rolled.values())
        cur=lambda k:submitted(k,"本期申请")
        opening=lambda k:submitted(k,"上期末累计")
        closing=lambda k:submitted(k,"本期末累计")
        for k in categories:checks["current_rollup"].append(rollup_valid[k] and cur(k)==rolled[k])
        checks["advances"] += [
            cur("工程预付款")==0,
            cur("材料预付款")==ref["material_new"],
            cur("材料预付款扣回")==ref["material_recovery"],
            cur("工程预付款扣回")==min(max(money(earned*ref["rates"]["工程预付款"]),Decimal(0)),ref["opening"]["工程预付款"]-ref["opening"]["工程预付款扣回"])]
        checks["retention_other"] += [cur("保留金")==money(earned*ref["rates"]["保留金"]),cur("其他扣款")==ref["other"]]
        additions=categories+["工程预付款","材料预付款"]
        deductions=["工程预付款扣回","材料预付款扣回","保留金","其他扣款"]
        for k in additions+deductions:
            o,c,n=opening(k),cur(k),closing(k)
            checks["cumulative"] += [o==ref["opening"][k],o is not None and c is not None and n==o+c]
        for col in ["上期末累计","本期申请","本期末累计"]:
            vals={k:submitted(k,col) for k in additions+deductions+["应付款金额合计","扣除金额合计","进度付款申请金额"]}
            complete=all(v is not None for v in vals.values())
            if complete:
                a=sum(vals[k] for k in additions);b=sum(vals[k] for k in deductions)
                checks["summary_arithmetic"] += [vals["应付款金额合计"]==a,vals["扣除金额合计"]==b,vals["进度付款申请金额"]==a-b]
            else:checks["summary_arithmetic"] += [False,False,False]
        # Match an adopted current request, not an arbitrary number somewhere in the letter.
        # A DOCX table can place the label and its amount in adjacent cells/lines.
        # Bind the adopted current-request amount across that local row boundary,
        # while stopping before cumulative/closing amounts.
        letter_lines = letter.splitlines()
        adopted=[]
        for index, line in enumerate(letter_lines):
            if not re.search(r"(?:本期.*申请.*金额|申请金额)", line):
                continue
            for nearby in letter_lines[index:index + 3]:
                current_part=re.split(r"截至|累计", nearby, maxsplit=1)[0]
                numbers=re.findall(r"[¥￥]?\s*([0-9][0-9,，]*\.\d+)", current_part)
                if numbers:
                    adopted.append(dec(numbers[0].replace(",","").replace("，","")))
                    break
        checks["letter_and_balances"].append(bool(adopted) and cur("进度付款申请金额") is not None and all(x==cur("进度付款申请金额") for x in adopted))
        checks["letter_and_balances"] += [
            None not in [balance("工程预付款期末余额"),opening("工程预付款"),opening("工程预付款扣回"),cur("工程预付款"),cur("工程预付款扣回")] and balance("工程预付款期末余额")==opening("工程预付款")-opening("工程预付款扣回")+cur("工程预付款")-cur("工程预付款扣回"),
            None not in [balance("材料预付款期末余额"),opening("材料预付款"),opening("材料预付款扣回"),cur("材料预付款"),cur("材料预付款扣回")] and balance("材料预付款期末余额")==opening("材料预付款")-opening("材料预付款扣回")+cur("材料预付款")-cur("材料预付款扣回"),
            balance("本期已完工程价款")==earned]
        # Duplicated amounts must agree with the candidate's own summary.
        for item,category in [("保留金","保留金"),("工程预付款本期扣回","工程预付款扣回"),("材料预付款本期新增","材料预付款"),("材料预付款本期扣回","材料预付款扣回"),("其他扣款","其他扣款")]:
            checks["letter_and_balances"].append(balance(item)==cur(category))
        checks["letter_and_balances"].append(None not in [balance("工程预付款期初余额"),opening("工程预付款"),opening("工程预付款扣回")] and balance("工程预付款期初余额")==opening("工程预付款")-opening("工程预付款扣回"))
        weights={"eligible_lines":.25,"line_arithmetic":.10,"current_rollup":.10,"advances":.15,"retention_other":.10,"cumulative":.10,"summary_arithmetic":.10,"letter_and_balances":.10}
        groups={k:sum(v)/len(v) if v else 0 for k,v in checks.items()}
        # Within the cross-file group, the adopted amount in the submission
        # letter is the authorization-facing control. Supporting duplicated
        # balances are useful reconciliation evidence but do not carry equal
        # payment exposure individually.
        letter_checks=checks["letter_and_balances"]
        groups["letter_and_balances"]=(
            .70*float(letter_checks[0])
            + .30*sum(letter_checks[1:])/len(letter_checks[1:])
        ) if len(letter_checks)>1 else float(bool(letter_checks and letter_checks[0]))
        score=sum(weights[k]*groups[k] for k in weights)
        return dict(measurement_complete=True,passed=all(v and all(v) for v in checks.values()),score=round(score,8),checks=checks,groups=groups,uncached_formula_cells=uncached_formulas)
    except Unmeasured:raise
    except Exception as e:return dict(measurement_complete=True,passed=False,score=0,reason=str(e))
def main():
    p=argparse.ArgumentParser();p.add_argument("--submission-dir",type=Path,required=True);p.add_argument("--input",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    try:r=verify(a.submission_dir,a.input)
    except Exception as e:r=dict(measurement_complete=False,passed=False,score=None,reason=str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(r,ensure_ascii=False));return 0 if r["passed"] else 1 if r["measurement_complete"] else 2
if __name__=="__main__":raise SystemExit(main())
