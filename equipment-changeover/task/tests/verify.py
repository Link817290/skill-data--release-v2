from pathlib import Path
import argparse,json,re,math
from docx import Document
HERE=Path(__file__).resolve().parent
NUMBER=r'[-+]?[0-9]+(?:[.][0-9]+)?'

def numbers(text):
    return [float(value) for value in re.findall(NUMBER,text.replace(',',''))]

def setting_value(text):
    """Return one unambiguous configured result, not the first number in prose."""
    text=text.replace('：',':').replace('＝','=')
    labelled=[float(value) for value in re.findall(
        r'(?:标签宽度|成品宽度|宽度设置|设置值|最终设置|取值)\s*(?:\([^)]*\))?\s*(?:为|:|=)?\s*('+NUMBER+r')',text,re.I)]
    if labelled and len(set(labelled))==1:return labelled[0]
    rhs=[float(value) for value in re.findall(r'(?:=|设置(?:值)?(?:为|:)?|取值(?:为|:)?|结果(?:为|:)?)\s*('+NUMBER+r')',text)]
    if rhs and len(set(rhs))==1:return rhs[0]
    values=numbers(text)
    return values[0] if len(values)==1 else None

def pressure_pair(text):
    text=text.replace('：',':').replace('／','/').replace('，',',')
    inside=re.search(r'内(?:侧|压|压力)?\s*(?:为|:|=)?\s*('+NUMBER+r')',text)
    outside=re.search(r'外(?:侧|压|压力)?\s*(?:为|:|=)?\s*('+NUMBER+r')',text)
    if inside and outside:return [float(inside.group(1)),float(outside.group(1))]
    values=numbers(text)
    return values if len(values)==2 else None

def check(submission):
    d=Document(submission/'包装工位标签打印作业指导书.docx');facts=json.loads((HERE/'reference/facts.json').read_text(encoding='utf8'))
    headers=['作业','打印类型','标签类型','收纸方式','宽度设置（点）','色带选择','压力起点（内/外）','放行条件']
    candidates=[]
    for tab in d.tables:
        h=[c.text.strip() for c in tab.rows[0].cells]
        if set(headers)<=set(h):candidates.append((tab,h))
    if len(candidates)!=1:return dict(passed=False,score=0,measurement_complete=True,checks=[{'id':'parameter_table','passed':False}])
    tab,h=candidates[0];rows={};duplicates=[]
    for row in tab.rows[1:]:
        values=[c.text.strip() for c in row.cells];k=values[h.index('作业')]
        if not k:continue
        if k in rows:duplicates.append(k)
        rows[k]=dict(zip(h,values))
    out=[dict(id='job_coverage',passed=set(rows)==set('ABCD') and not duplicates,weight=.15)]
    for k,f in facts['jobs'].items():
        r=rows.get(k,{})
        width=setting_value(r.get('宽度设置（点）',''))
        pressure=pressure_pair(r.get('压力起点（内/外）',''))
        out.append(dict(id=k+'_width',passed=width==f['width'],weight=.55/3,observed=width))
        out.append(dict(id=k+'_pressure',passed=pressure==f['pressure'],weight=.30/3,observed=pressure))
    return dict(passed=all(c['passed'] for c in out),score=round(sum(c['weight'] for c in out if c['passed']),8),measurement_complete=True,checks=out)
def main():
    p=argparse.ArgumentParser();p.add_argument('--submission-dir',type=Path,required=True);p.add_argument('--input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:r=check(a.submission_dir)
    except Exception as e:r=dict(passed=False,score=0,measurement_complete=True,artifact_error=type(e).__name__)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(r));return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
