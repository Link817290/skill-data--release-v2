from pathlib import Path
import argparse,json,datetime as dt,calendar,re
from openpyxl import load_workbook
from openpyxl.styles.numbers import is_datetime
HERE=Path(__file__).resolve().parent
def date(v):
    if isinstance(v,dt.datetime):return v.date()
    if isinstance(v,dt.date):return v
    return dt.date.fromisoformat(str(v).strip()[:10])
def moment(v):
    if isinstance(v,dt.datetime):return v
    if isinstance(v,dt.date):return dt.datetime.combine(v,dt.time(16))
    return dt.datetime.fromisoformat(str(v).replace('/','-'))
def displayed_moment(value,cell,description):
    actual=dt.datetime.combine(value,dt.time(0)) if isinstance(value,dt.date) and not isinstance(value,dt.datetime) else moment(value)
    # A date-only cell can state its clock time in the adjacent explanation.
    clocks={(int(hour),int(minute)) for hour,minute in re.findall(r'(?<!\d)([01]?\d|2[0-3])[:：]([0-5]\d)(?!\d)',str(description or ''))}
    if len(clocks)==1:
        declared=dt.time(*next(iter(clocks)))
        if actual.time()==dt.time(0) and is_datetime(cell.number_format)=='date':return dt.datetime.combine(actual.date(),declared)
        if actual.time()!=declared:return None
    return actual
def addmonth(v):
    y=v.year+(v.month==12);m=v.month%12+1
    return v.replace(year=y,month=m,day=min(v.day,calendar.monthrange(y,m)[1]))
def records(s,key):
    data=list(s.values);h=next(i for i,r in enumerate(data) if key in r)
    headers=data[h];return [dict(zip(headers,row)) for row in data[h+1:] if any(v is not None for v in row)]
def annotation(row,key,fields):
    return (isinstance(row.get(key),str)
            and re.match(r'^(?:注[：:]|Note[：:])',row[key].strip(),re.IGNORECASE)
            and all(row.get(field) in (None,'') for field in fields))
def fill_key(cell):
    if cell.fill.patternType!='solid':return None
    color=cell.fill.fgColor
    if color.type=='rgb':return ('rgb',color.rgb[-6:].upper(),color.tint)
    if color.type=='indexed':return ('indexed',color.indexed,color.tint)
    if color.type=='theme':return ('theme',color.theme,color.tint)
    return None

def legend_role(text):
    text=str(text or '').strip()
    if re.search(r'停工|不施工|无施工|无作业|无计划施工|non.?working|no work',text,re.IGNORECASE):return False
    if re.search(r'施工|作业|机务组|电试组|继保组|直流组|work(?:ing)?',text,re.IGNORECASE):return True
    return None

def gantt_colors(sheet,first_row):
    colors={};conflicts=set();inside_legend=False
    def add(color,role):
        if color is None or role is None:return
        if color in colors and colors[color]!=role:conflicts.add(color)
        colors[color]=role
    for row in sheet.iter_rows(min_row=first_row):
        if any(re.search(r'图例|legend',str(cell.value or ''),re.IGNORECASE) for cell in row):inside_legend=True
        if not inside_legend:continue
        for index,cell in enumerate(row):
            if fill_key(cell):
                label=cell.value
                if not label:
                    label=next((other.value for other in row[index+1:] if other.value is not None),'')
                add(fill_key(cell),legend_role(label))
            for match in re.finditer(r'(?i)(?<![0-9a-f])([0-9a-f]{6}|[0-9a-f]{8})\s*[）)]?\s*[=：:]\s*([^；;]+)',str(cell.value or '')):
                add(('rgb',match.group(1)[-6:].upper(),0.),legend_role(match.group(2)))
    return colors,conflicts

def gantt_package(value,packages):
    if value in packages:return value
    if not isinstance(value,str):return None
    match=re.fullmatch(r'([A-Z])包\s*[:：]\s*.+',value.strip())
    return match.group(1) if match and match.group(1) in packages else None

def gantt_active(cell,colors,conflicts):
    text=str(cell.value or '').strip()
    color=fill_key(cell)
    if color in conflicts:raise ValueError('Conflicting Gantt color legend')
    painted=colors.get(color)
    if text in ['','-','—','休','休息','0','停','停工','停工日','非施工','无施工','无作业']:
        if text and painted is True:raise ValueError('Gantt text contradicts its color legend')
        # In a declared day grid, a non-default solid fill is a conventional
        # work bar even when the template has no separate legend. Explicit
        # non-work text still wins; conflicting legends remain errors above.
        return painted is True if not text else False
    if painted is False:raise ValueError('Gantt work mark contradicts its nonworking legend')
    return True

def infer_grid_colors(rows,dates,colors,conflicts):
    seen={}
    for row in rows:
        for index in dates:
            if index>=len(row):continue
            cell=row[index];color=fill_key(cell)
            if color is None:continue
            seen.setdefault(color,[]).append((index,cell))
            role=legend_role(cell.value)
            if role is not None:
                if color in colors and colors[color]!=role:conflicts.add(color)
                colors[color]=role
    for color,cells in seen.items():
        if color in colors:continue
        per_column={index:0 for index in dates}
        for index,_ in cells:per_column[index]+=1
        colors[color]=not any(count==len(rows) for count in per_column.values())
    return colors,conflicts

def check(folder):
    f=json.loads((HERE/'reference/facts.json').read_text(encoding='utf8'));base=date(f['base_date']);P={p[0]:p for p in f['packages']}
    w=load_workbook(folder/'电力设备检修进度计划表.xlsx',data_only=True)
    checks=[]
    def add(k,b,weight,detail=''):checks.append(dict(id=k,passed=bool(b),weight=weight,detail=detail))
    rows=records(w['进度安排'],'工作包')
    # A single-cell annotation below the schedule does not add a work package.
    rows=[r for r in rows if not annotation(r,'工作包',['开始日期','结束日期','班组','机具'])]
    keys=[r['工作包'] for r in rows];by={r['工作包']:r for r in rows}
    add('scope',set(keys)==set(P) and len(keys)==len(P),.15)
    if not checks[-1]['passed']:return dict(passed=False,measurement_complete=True,score=0,checks=checks)
    spans={k:((date(r['开始日期'])-base).days,(date(r['结束日期'])-base).days) for k,r in by.items()}
    legal=all(e-s+1==P[k][5] and s in f['starts'][k] for k,(s,e) in spans.items())
    add('duration_windows',legal,.20)
    overlap=lambda a,b:spans[a][0]<=spans[b][1] and spans[b][0]<=spans[a][1]
    correct_resources=all(by[k]['班组']==P[k][3] and by[k]['机具']==P[k][4] for k in P)
    collisions=[(a,b) for i,a in enumerate(P) for b in list(P)[i+1:] if (P[a][3]==P[b][3] or P[a][4]==P[b][4]) and overlap(a,b)]
    add('resource_feasibility',correct_resources and not collisions,.15,str(collisions))
    dependency=spans['T'][0]>spans['M'][1]
    add('coupled_precedence',dependency,.10)
    obj=[spans['T'][1],max(e for s,e in spans.values())]
    add('documented_priorities',legal and correct_resources and not collisions and dependency and obj==f['lexicographic_best'],.15,str(obj))
    follow=[r for r in records(w['后续安排'],'事项') if not annotation(r,'事项',['关联包','计划时间'])];index={}
    follow_sheet=w['后续安排'];follow_data=list(follow_sheet.values)
    follow_header=next(i for i,row in enumerate(follow_data) if '事项' in row)
    follow_columns={value:i+1 for i,value in enumerate(follow_data[follow_header])}
    time_cells={(row[follow_columns['事项']-1],row[follow_columns['关联包']-1]):follow_sheet.cell(i+1,follow_columns['计划时间'])
                for i,row in enumerate(follow_data) if i>follow_header and any(value is not None for value in row)}
    duplicates=[]
    for r in follow:
        key=(r['事项'],r['关联包'])
        if key in index:duplicates.append(key)
        index[key]=r
    errs=[]
    for k in ['T','D','S','R','U','B']:
        expected=dt.datetime.combine(base+dt.timedelta(days=spans[k][1]),dt.time(16))
        for name,when in [('候选送电',expected),('保运结束',expected+dt.timedelta(hours=48))]:
            actual=index.get((name,k),{}).get('计划时间')
            if actual is None or displayed_moment(actual,time_cells[(name,k)],index[(name,k)].get('条件或说明'))!=when:errs.append([name,k])
    actual=index.get(('报告提交期限','全部'),{}).get('计划时间');due=base+dt.timedelta(days=obj[1]+14)
    if actual is None or date(actual)!=due:errs.append(['报告提交期限'])
    actual=index.get(('油跟踪分析','T'),{}).get('计划时间');due=addmonth(base+dt.timedelta(days=spans['T'][1]))
    if actual is None or date(actual)!=due:errs.append(['油跟踪分析'])
    add('followup_calendar',not errs and not duplicates,.15,str(errs))
    g=w['日历进度'];data=list(g.iter_rows());header=next(i for i,r in enumerate(data[:12]) if r[0].value=='工作包');data=data[header:];dates={i:(date(cell.value)-base).days for i,cell in enumerate(data[0]) if i and cell.value is not None}
    # The calendar may contain explanatory legend rows below the seven package
    # rows. Recognizable package IDs may include their descriptive names.
    package_rows=[r for r in data[1:] if gantt_package(r[0].value,P)]
    gr={gantt_package(r[0].value,P):r for r in package_rows};consistent=(set(gr)==set(P) and len(package_rows)==len(P)
        and set(dates.values())==set(range(15)))
    colors,conflicts=gantt_colors(g,header+len(P)+2)
    colors,conflicts=infer_grid_colors(package_rows,dates,colors,conflicts)
    for k,row in gr.items():
        if k not in spans:consistent=False;continue
        try:active={day for i,day in dates.items() if i<len(row) and gantt_active(row[i],colors,conflicts)}
        except ValueError:consistent=False;continue
        if active!=set(range(spans[k][0],spans[k][1]+1)):consistent=False
    add('gantt_consistency',consistent,.10)
    return dict(passed=all(c['passed'] for c in checks),score=round(sum(c['weight'] for c in checks if c['passed']),8),measurement_complete=True,checks=checks)
def main():
    p=argparse.ArgumentParser();p.add_argument('--submission-dir',type=Path,required=True);p.add_argument('--input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:r=check(a.submission_dir)
    except Exception as e:r=dict(passed=False,score=0,measurement_complete=True,artifact_error=type(e).__name__+': '+str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(r));return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
