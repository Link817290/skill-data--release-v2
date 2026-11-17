"""Rebuild the quality register from the supplied notice dossier. No network access."""
import argparse,json,re,shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches
from docx.oxml.ns import qn

def date_value(text):
    text=re.sub(r'\s+',' ',str(text).strip())
    for fmt in ('%b %d %y','%d %b %y','%Y-%m-%d'):
        try:return datetime.strptime(text,fmt).date().isoformat()
        except ValueError:pass
    raise ValueError('Unrecognised notice date: '+text)

def size_value(text):
    text=re.sub(r'\s+','',str(text).lower()).replace('bag','')
    text=text.replace('lbs','lb')
    if 'pk/' in text:
        m=re.fullmatch(r'(\d+)pk/(\d+(?:\.\d+)?)lb',text)
        if not m:raise ValueError('Unrecognised multipack: '+text)
        return f'{m[1]} pk / {m[2]} lb'
    m=re.fullmatch(r'(\d+(?:\.\d+)?)(lb|oz)',text)
    if not m:raise ValueError('Unrecognised package size: '+text)
    return f'{m[1]} {m[2]}'

def read_tables(input_dir):
    import fitz
    groups={}
    for path in sorted((input_dir/'supplier-notices').glob('*.pdf')):
        with fitz.open(path) as document:
            for page in document:
                for table in page.find_tables().tables:
                    rows=table.extract()
                    if not rows or not rows[0] or rows[0][0]!='Ref.':continue
                    for row in rows[1:]:
                        row=[re.sub(r'\s+',' ',str(c or '')).strip() for c in row]
                        reference=row[0]
                        if not re.fullmatch(r'N0[1-4]-[WBP]\d{2}',reference):raise ValueError('Unexpected notice reference: '+reference)
                        if reference in groups:raise ValueError('Duplicate notice record: '+reference)
                        groups[reference]=row
    prefixes=['N01-W','N01-B','N02-W','N03-P','N04-P']
    result=[[groups[key] for key in sorted(groups) if key.startswith(prefix)] for prefix in prefixes]
    if [len(g) for g in result]!=[15,18,3,2,9]:raise ValueError('Incomplete supplier notice tables')
    return result

def solve(input_dir):
    whole,baby,expanded,fs,earth=read_tables(input_dir)
    scopes={};changes=[];channels=[]
    def add(company,brand,product,size,upc,kind,start,end,c0,c1,ref):
        key=(company,brand,product,size,upc,kind,start,end,c0,c1)
        scopes.setdefault(key,set()).add(ref)
    baseline=set()
    for ref,brand,sizes in whole:
        for raw in sizes.split(','):
            size=size_value(raw);baseline.add((brand,size))
            add('Grimmway Farms',brand,'Organic Whole Carrots',size,'','Retail sale period','2024-08-14','2024-10-23','','',ref)
    for ref,brand,sizes in expanded:
        for raw in sizes.split(','):
            size=size_value(raw)
            add('Grimmway Farms',brand,'Organic Whole Carrots',size,'','Retail sale period','2024-08-14','2024-10-23','','',ref)
            if (brand,size) not in baseline:changes.append([brand,'Organic Whole Carrots',size,'Added','2024-11-21',ref])
    for ref,brand,sizes,start,end in baby:
        for raw in sizes.split(','):
            add('Grimmway Farms',brand,'Organic Baby Carrots',size_value(raw),'','Best-if-Used-by',date_value(start),date_value(end),'','',ref)
    for ref,brand,product,size in fs:
        add('F&S Fresh Foods',brand,product,size_value(size),'','Best if sold by','2024-09-01','2024-10-19','GH236','GH284',ref)
        channels.append(['F&S Fresh Foods',brand,product,size_value(size),'','Whole Foods Market','AZ;CA;HI;ID;NV',ref])
    for ref,description,brand,channel in earth:
        m=re.search(r'(\d+\s*(?:oz|lb))',description);size=size_value(m[1])
        product=description[:m.start()].strip()
        upc_match=re.search(r'UPC\s*(\d+)',description);upc=upc_match[1] if upc_match else ''
        add('4Earth Farms',brand,product,size,upc,'Best by','2024-09-07','2024-11-02','','',ref)
        channels.append(['4Earth Farms',brand,product,size,upc,channel,'NH;FL;CA;PA;MN;IL;CO',ref])
    rows=[list(key)+[';'.join(sorted(refs))] for key,refs in sorted(scopes.items())]
    w=[r for r in rows if r[0]=='Grimmway Farms' and r[2]=='Organic Whole Carrots']
    b=[r for r in rows if r[0]=='Grimmway Farms' and r[2]=='Organic Baby Carrots']
    e=[r for r in rows if r[0]=='4Earth Farms']
    counts=[len({r[1] for r in w}),len(w),len(changes),len({r[1] for r in b}),len(b),len(fs),len(earth),len(e),len({r[5] for r in channels if r[0]=='4Earth Farms'}),7,5,len(rows)]
    return dict(scopes=rows,changes=sorted(changes),channels=sorted(channels),counts=counts)

def write_outputs(input_dir,out):
    import csv
    from presentation import write_report
    data=solve(input_dir);out.mkdir(parents=True,exist_ok=True)
    schemas={}
    with (input_dir/'register-fields.csv').open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):schemas.setdefault(row['File'],[]).append(row['Column'])
    for name,key in [('product-scope.csv','scopes'),('pack-changes.csv','changes'),('distribution-list.csv','channels')]:
        with (out/name).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(schemas[name]);writer.writerows(data[key])
    write_report(out,data)
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();data=write_outputs(a.input,a.out);print(json.dumps(dict(scope_count=len(data['scopes']),counts=data['counts'])))
