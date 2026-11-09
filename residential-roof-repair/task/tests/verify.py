"""Independent enquiry quantity checks against the public schedules, not Golden."""
import argparse,json,math,re
from pathlib import Path
from openpyxl import load_workbook

TASK=Path(__file__).resolve().parents[1]
PACKAGE=TASK
EXPECTED=['甲-01','甲-02','甲-03','甲-04','甲-05','甲-06','甲-07','乙-03','乙-04','乙-11','乙-12','乙-13','乙-18','丙-03','丙-04','丙-07','丙-08','丙-09','丙-10']
PENDING={'乙-18','丙-10'}
GROUPS={'Q01':['甲-03','甲-04','乙-11','乙-12','丙-08'],'Q02':['甲-02','乙-03','乙-04','丙-04'],'Q03':['甲-01'],'Q04':['甲-06'],'Q05':['丙-03'],'Q06':['丙-07'],'Q07':['甲-05','乙-13','丙-09'],'Q08':['甲-07']}
UNITS={'Q01':'m2','Q02':'m2','Q03':'m2','Q04':'m2','Q05':'m2','Q06':'m2','Q07':'m','Q08':'m3'}

class Unmeasured(Exception):pass

def number(value):
    if isinstance(value,bool):raise ValueError('Boolean is not a quantity')
    n=float(str(value).replace(',','').strip())
    if not math.isfinite(n):raise ValueError('Nonfinite quantity')
    return n

def unit(value):
    s=str(value).strip().lower().replace('²','2').replace('³','3')
    return {'㎡':'m2','平方米':'m2','平方':'m2','立方米':'m3','米':'m'}.get(s,s)

def records(ws,key,required):
    for row in ws.iter_rows(min_row=1,max_row=min(12,ws.max_row)):
        vals=[c.value for c in row]
        if key in vals:
            if any(vals.count(h)!=1 for h in required):raise ValueError('Missing/duplicate public field in '+ws.title)
            columns={h:vals.index(h)+1 for h in required};start=row[0].row+1;break
    else:raise ValueError('Public header not found in '+ws.title)
    result={}
    for r in range(start,ws.max_row+1):
        value=ws.cell(r,columns[key]).value
        if value in (None,''):continue
        identifier=str(value).strip()
        if identifier in result:raise ValueError('Duplicate identifier '+identifier)
        result[identifier]={h:ws.cell(r,c).value for h,c in columns.items()}
    return result

def source_records(input_dir):
    wb=load_workbook(input_dir/'分部分项工程量清单.xlsx',data_only=True)
    result={}
    for name in ['甲区住宅楼','乙区住宅楼','丙区住宅楼']:
        result.update(records(wb[name],'清单索引',['清单索引','项目编码','项目名称及特征','计量单位','工程数量']))
    if not set(EXPECTED)<=set(result):raise Unmeasured('Author source schedule is incomplete')
    return result

def verify(path,input_dir):
    try:src=source_records(input_dir)
    except (OSError,ValueError,KeyError,TypeError) as exc:raise Unmeasured('Author source unavailable or malformed: '+str(exc)) from exc
    wb=load_workbook(path,data_only=True);formula=load_workbook(path,data_only=False)
    for name in ['询价清单','数量汇总']:
        if name not in wb:raise ValueError('Missing public sheet '+name)
        for row in formula[name]:
            for c in row:
                if c.data_type=='f' and wb[name][c.coordinate].value is None:raise Unmeasured('Formula cache unavailable: '+name+'!'+c.coordinate)
    quoted=records(wb['询价清单'],'清单索引',['清单索引','项目编码','项目名称及特征','计量单位','工程数量','综合单价','合价','备注'])
    summary=records(wb['数量汇总'],'汇总编号',['汇总编号','项目内容','单位','工程数量','说明'])
    known=set(EXPECTED)-PENDING;errors=[];correct=0
    for key in sorted(known):
        row=quoted.get(key)
        try:ok=row is not None and str(row['项目编码']).strip()==str(src[key]['项目编码']) and unit(row['计量单位'])==unit(src[key]['计量单位']) and abs(number(row['工程数量'])-number(src[key]['工程数量']))<=.005
        except (ValueError,TypeError):ok=False
        if ok:correct+=1
        else:errors.append(key)
    unexpected=[k for k,r in quoted.items() if k not in EXPECTED and (r['工程数量'] not in (None,'') or r['项目编码'] not in (None,''))]
    pending_ok=[]
    for key in sorted(PENDING):
        r=quoted.get(key)
        good=r is not None and unit(r['计量单位'])=='m3' and str(r['项目编码']).strip()==str(src[key]['项目编码']) and r['工程数量'] in (None,'','待核','待复核','待确认','未核定','待核定') and bool(str(r['备注'] or '').strip())
        pending_ok.append({'id':key,'passed':good})
    sums=[]
    for key,ids in GROUPS.items():
        row=summary.get(key);own=[]
        try:
            for rid in ids:own.append(number(quoted[rid]['工程数量']))
        except (ValueError,TypeError,KeyError):
            sums.append({'id':key,'passed':False,'dependent_check':'Upstream quantity unavailable; summary cannot be independently reconciled.'});continue
        try:good=row is not None and unit(row['单位'])==UNITS[key] and abs(number(row['工程数量'])-sum(own))<=.005
        except (ValueError,TypeError):good=False
        sums.append({'id':key,'passed':good,'independent_sum_of_submitted_rows':round(sum(own),6)})
    fabricated=[k for k,r in quoted.items() if any(r[h] not in (None,'','待报价','待报','待填') for h in ['综合单价','合价'])]
    expected_rows_present=all(key in quoted for key in EXPECTED)
    line_score=max(0.0,(correct-len(unexpected))/len(known))
    checks={'known_scope_quantities':{'score':line_score,'failed_ids':errors,'unexpected_scope_ids':unexpected},'unresolved_waste':{'score':float(all(x['passed'] for x in pending_ok)),'details':pending_ok},'summary_reconciliation':{'score':sum(x['passed'] for x in sums)/len(sums),'details':sums},'quotation_status':{'score':float(expected_rows_present and not fabricated),'unsupported_price_ids':fabricated,'expected_rows_present':expected_rows_present}}
    score=round(sum(c['score'] for c in checks.values())/len(checks),8)
    return {'measurement_complete':True,'passed':score==1,'score':score,'checks':checks,'source':'Public input reconstructed independently; no Golden import','rollout_executed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--workbook',type=Path,default=Path('/workspace/output/维修询价清单.xlsx'));p.add_argument('--input',type=Path,default=TASK/'environment/workspace/input');p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    dest=a.report.resolve()
    if dest==PACKAGE or PACKAGE in dest.parents:raise ValueError('Receipts belong outside the package')
    try:r=verify(a.workbook,a.input)
    except Unmeasured as exc:r={'passed':False,'score':None,'measurement_complete':False,'error':str(exc)}
    except (ValueError,KeyError,OSError,TypeError) as exc:r={'passed':False,'score':0,'measurement_complete':True,'error':str(exc)}
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(r,ensure_ascii=False));return 0 if r['passed'] else (1 if r['measurement_complete'] else 2)
if __name__=='__main__':raise SystemExit(main())
