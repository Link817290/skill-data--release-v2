"""Static checks for a current-format Shopify product CSV; no source-data truth claims."""
import argparse,csv,json,re
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal,InvalidOperation
def inspect(path):
    errors=[];warnings=[]
    try:
        with Path(path).open(encoding='utf-8-sig',newline='') as f:
            r=csv.DictReader(f);heads=r.fieldnames or [];rows=list(r)
    except Exception as e:return {'passed':False,'errors':['CSV unreadable: '+str(e)],'warnings':[]}
    required={'URL handle','Title','SKU','Option1 name','Option1 value','Price'}
    if not required.issubset(heads) or len(heads)!=len(set(heads)):
        return {'passed':False,'errors':['Missing or duplicate headers'],'warnings':[]}
    groups=defaultdict(list);skus=Counter()
    for line,r in enumerate(rows,2):
        if None in r or any(v is None for v in r.values()):errors.append(f'line {line}: row length');continue
        h=r['URL handle'].strip();groups[h].append((line,r));skus[r['SKU']]+=1
        if not h or re.search(r'\s',h):errors.append(f'line {line}: handle')
        if not r['SKU'].strip():warnings.append(f'line {line}: blank SKU; check merchant identifier requirements')
        if not r['Option1 name'].strip() or not r['Option1 value'].strip():errors.append(f'line {line}: option1 dependency')
        for n in (2,3):
            if bool(r.get(f'Option{n} name','').strip())!=bool(r.get(f'Option{n} value','').strip()):errors.append(f'line {line}: option{n} dependency')
        try:
            val=Decimal(r['Price'])
            if not val.is_finite() or val<0:raise InvalidOperation
        except InvalidOperation:errors.append(f'line {line}: numeric nonnegative price')
        if r.get('Status') and r['Status'].lower() not in {'draft','active','archived'}:errors.append(f'line {line}: status')
        for k in ['Published on online store','Requires shipping','Charge tax']:
            if r.get(k) and r[k].lower() not in {'true','false'}:errors.append(f'line {line}: {k}')
        if r.get('Description') and re.search(r'<(?:script|iframe)\b|\bon\w+\s*=',r['Description'],re.I):errors.append(f'line {line}: unsafe HTML')
    for h,items in groups.items():
        lines=[i for i,_ in items]
        if lines!=list(range(min(lines),max(lines)+1)):errors.append(f'{h}: noncontiguous rows')
        if not items[0][1]['Title'].strip():errors.append(f'{h}: missing first-row title')
        tuples=[]
        option_names=None
        for _,r in items:
            names=tuple(r.get(f'Option{n} name','').strip().lower() for n in (1,2,3))
            if option_names is None:option_names=names
            elif names!=option_names:errors.append(f'{h}: inconsistent option names')
            tuples.append(tuple(r.get(f'Option{n} value','').strip().lower() for n in (1,2,3)))
        if len(tuples)!=len(set(tuples)):errors.append(f'{h}: duplicate option tuple')
    if any(k and n>1 for k,n in skus.items()):errors.append('Repeated nonempty SKU')
    return {'passed':not errors,'products':len(groups),'rows':len(rows),'errors':errors,'warnings':warnings,
            'scope':'Static mechanics only; no assortment, specification or live-store verification.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    result=inspect(a.file);text=json.dumps(result,indent=2)
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(text+'\n',encoding='utf-8')
    print(text)
