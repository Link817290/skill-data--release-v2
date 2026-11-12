"""Independent import contract checks. No comparison with Golden copy or handles."""
from pathlib import Path
from decimal import Decimal,InvalidOperation
from collections import Counter,defaultdict
import argparse,csv,json,re
from html.parser import HTMLParser
import fitz
def norm(v):return re.sub(r'\s+','',str(v or '')).casefold()
def pack(v):return re.sub(r'[\s_-]+','',str(v or '')).casefold()
def read_assortment_pdf(path):
    """Extract only the published detailed assortment tables, not private facts."""
    headers=['系列','商品名称','颜色','销售规格','货号','首发零售价USD']
    records=[]
    with fitz.open(path) as document:
        for page in document:
            for table in page.find_tables().tables:
                rows=table.extract()
                header_indices=[i for i,row in enumerate(rows)
                                if [re.sub(r'\s+','',v or '') for v in row]==headers]
                if not header_indices:continue
                if len(header_indices)!=1:raise ValueError('Ambiguous assortment header')
                start=header_indices[0]+1
                for index,row in enumerate(rows[start:],start):
                    if len(row)!=6 or any(value is None or not value.strip() for value in row):
                        raise ValueError('Incomplete assortment table row')
                    # PDF text streams emit the underscore separately. These
                    # SKU cells are visually single-line: retain every character
                    # and rebuild its actual left-to-right order within the cell.
                    box=table.rows[index].cells[4]
                    if box is None:raise ValueError('SKU cell boundary unavailable')
                    raw=page.get_text('rawdict',clip=fitz.Rect(box))
                    chars=[char for block in raw['blocks'] for line in block.get('lines',[])
                           for span in line['spans'] for char in span['chars'] if not char['c'].isspace()]
                    sku=''.join(char['c'] for char in sorted(chars,key=lambda char:char['bbox'][0]))
                    if not re.fullmatch(r'[A-Z0-9]+_[A-Z0-9/]+',sku):
                        raise ValueError('SKU cell cannot be reconstructed reliably')
                    series,name,color,sales_pack=(
                        re.sub(r'\s+','',value) for value in row[:4])
                    price_text=re.sub(r'[\s$,]','',row[5])
                    if not re.fullmatch(r'\d+(?:\.\d{1,2})?',price_text):
                        raise ValueError('Invalid published retail price')
                    records.append((series,name,color,sales_pack,sku,Decimal(price_text)))
    if len(records)!=33 or len({r[4] for r in records})!=33:
        raise ValueError('Published assortment cannot be read completely and uniquely')
    return records
def verify(submission_dir,input_dir):
    try:
        input_dir=Path(input_dir)
        with (input_dir/'products-template.csv').open(encoding='utf-8-sig',newline='') as f:expected_headers=next(csv.reader(f))
        expected={}
        for r in read_assortment_pdf(input_dir/'美国站露营椅选款.pdf'):
            expected[str(r[4])]={'series':r[0],'color':r[2],'pack':r[3] if 'pack' in str(r[3]).lower() else None,'price':Decimal(str(r[5]))}
        if len(expected)!=33:raise ValueError('Input range cannot be read completely.')
    except Exception as e:return {'measurement_complete':False,'passed':False,'score':None,'error':'Input/reference unavailable: '+str(e)}
    file=Path(submission_dir)/'products.csv'
    if not file.is_file():return {'measurement_complete':True,'passed':False,'score':0.0,'checks':{'delivery':False},'details':{'missing':'products.csv'}}
    try:
        with file.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);headers=reader.fieldnames or [];rows=list(reader)
        schema=len(headers)==len(set(headers)) and set(headers)==set(expected_headers) and all(None not in r for r in rows)
    except Exception as e:return {'measurement_complete':True,'passed':False,'score':0.0,'checks':{'readable_csv':False},'details':{'error':str(e)}}
    if not schema:return {'measurement_complete':True,'passed':False,'score':0.0,'checks':{'schema':False},'details':{'headers':headers,'expected_headers':expected_headers}}
    for r in rows:
        for k in headers:r[k]=(r[k] or '').strip()
    counts=Counter(r['SKU'] for r in rows)
    missing=sorted(set(expected)-set(counts));extra=sorted(set(counts)-set(expected));duplicates=sorted(k for k,v in counts.items() if v>1)
    good=[r for r in rows if r['SKU'] in expected and counts[r['SKU']]==1]
    errors=defaultdict(list)
    groups=defaultdict(list)
    for i,r in enumerate(rows,2):groups[r['URL handle']].append((i,r))
    series_handles=defaultdict(set)
    handle_series=defaultdict(set)
    series_option_orders=defaultdict(set)
    for r in good:
        e=expected[r['SKU']];series_handles[e['series']].add(r['URL handle']);handle_series[r['URL handle']].add(e['series'])
        option_names=[norm(r['Option1 name'])]
        if r['Option2 name']:option_names.append(norm(r['Option2 name']))
        series_option_orders[e['series']].add(tuple(option_names))
        opts={norm(r['Option1 name']):r['Option1 value']}
        if r['Option2 name']:opts[norm(r['Option2 name'])]=r['Option2 value']
        want={'color':e['color']}
        if e['pack']:want['pack']=e['pack']
        ok=len(option_names)==len(set(option_names)) and set(opts)==set(want) and all((pack(opts[k])==pack(v) if k=='pack' else norm(opts[k])==norm(v)) for k,v in want.items())
        if not r['Option2 name'] and r['Option2 value']:ok=False
        if not ok:errors['options'].append(r['SKU'])
        try:priceok=Decimal(r['Price'])==e['price'] and re.fullmatch(r'\d+(?:\.\d{1,2})?',r['Price']) is not None
        except InvalidOperation:priceok=False
        if not priceok:errors['price'].append(r['SKU'])
        settings={'Status':'draft','Published on online store':'false','Charge tax':'true','Continue selling when out of stock':'deny','Requires shipping':'true','Fulfillment service':'manual'}
        if any(norm(r[k])!=v for k,v in settings.items()) or r['Inventory tracker'] or r['Compare-at price']:errors['staging'].append(r['SKU'])
    for h,rs in groups.items():
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',h or ''):errors['grouping'].append('invalid handle '+h)
        seq=[i for i,_ in rs]
        if seq!=list(range(min(seq),max(seq)+1)):errors['grouping'].append(h+': interleaved product')
    # Product-row structure belongs to the source series, independently of a
    # submitted handle typo. Do not charge that typo again as missing copy/tags.
    product_rows=defaultdict(list)
    expected_by_series=defaultdict(set)
    for sku,e in expected.items():expected_by_series[e['series']].add(sku)
    for i,r in enumerate(rows,2):
        if r['SKU'] in expected:product_rows[expected[r['SKU']]['series']].append((i,r))
    for series,rs in product_rows.items():
        # An omitted/duplicated source row is owned by range; it cannot establish
        # which product-head fields the absent row would have carried.
        if {r['SKU'] for _,r in rs}!=expected_by_series[series] or any(counts[r['SKU']]!=1 for _,r in rs):continue
        h=str(series)
        first=rs[0][1]
        if any(not first[k] for k in ['Title','Description']):errors['content'].append(h+': incomplete product row')
        if first['Vendor']!='KingCamp' or first['Type']!='Camping Chairs' or {x.strip() for x in first['Tags'].split(',')}!={'camping','us-launch'}:errors['staging'].append(h+': classification')
        if any(r[k] for _,r in rs[1:] for k in ['Title','Description','Vendor','Type','Tags']):errors['content'].append(h+': repeated product fields')
        if not re.search(r'<(?:p|ul|ol|div)\b',first['Description'],re.I) or re.search(r'<(?:script|iframe)\b|\bon\w+\s*=',first['Description'],re.I):errors['content'].append(h+': HTML body')
    if any(len(v)!=1 for v in series_handles.values()) or any(len(v)!=1 for v in handle_series.values()):errors['grouping'].append('series split or merged')
    for series,orders in series_option_orders.items():
        if len(orders)!=1:errors['options'].append(str(series)+': inconsistent option column order')
    checks={'schema':True,'range':not(missing or extra or duplicates),'grouping':not errors['grouping'],
            'options':not errors['options'],'prices':not errors['price'],'staging':not errors['staging'],'content_structure':not errors['content']}
    if not good:
        for k in ['grouping','options','prices','staging','content_structure']:checks[k]=False
    weights={'schema':.10,'range':.20,'grouping':.20,'options':.20,'prices':.15,'staging':.10,'content_structure':.05}
    score=round(sum(weights[k] for k,v in checks.items() if v),6)
    return {'measurement_complete':True,'passed':all(checks.values()),'score':score,'checks':checks,
            'details':{'expected_skus':len(expected),'submitted_rows':len(rows),'product_handles':len(groups),
                       'missing_skus':missing,'extra_skus':extra,'duplicate_skus':duplicates,'errors':dict(errors)}}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--submission-dir',type=Path,default=Path('/workspace/output'));p.add_argument('--input',type=Path,default=Path('/workspace/input'));p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    task=Path('/task') if Path('/task/instruction.md').is_file() else Path(__file__).resolve().parents[1]
    package=task.parent
    target=a.out.resolve();submission=a.submission_dir.resolve();inputs=a.input.resolve()
    protected=[submission,inputs]
    if package != Path('/'):
        protected.append(package)
    if any(target==root or root in target.parents for root in protected):
        raise SystemExit('Keep the receipt outside package, submission and input directories.')
    if target.exists():raise SystemExit('Use a new receipt file path.')
    try:result=verify(a.submission_dir,a.input)
    except Exception as error:result={'measurement_complete':False,'passed':False,'score':None,'error':str(error)}
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else (1 if result['measurement_complete'] else 2))
