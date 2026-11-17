"""Verify the published CSV registers against independently checked notice facts."""
import argparse,json,re,math
from collections import Counter
from datetime import date,datetime
from pathlib import Path
import csv
HERE=Path(__file__).resolve().parent
STATES={'ARIZONA':'AZ','CALIFORNIA':'CA','HAWAII':'HI','IDAHO':'ID','NEVADA':'NV','NEW HAMPSHIRE':'NH','FLORIDA':'FL','PENNSYLVANIA':'PA','MINNESOTA':'MN','ILLINOIS':'IL','COLORADO':'CO'}
def text(v):
 if v is None:return ''
 if isinstance(v,(date,datetime)):return v.date().isoformat() if isinstance(v,datetime) else v.isoformat()
 if isinstance(v,float) and v.is_integer():return str(int(v))
 return re.sub(r'\s+',' ',str(v).strip()).replace('’',"'").replace('‘',"'").replace('–','-').replace('—','-')
def package(v):
 s=text(v).lower().replace(' ','').replace('lbs','lb').replace('bag','')
 return s
def wording(v):
 return re.sub(r'[^a-z0-9]','',text(v).casefold())

def basis(v):
 key=wording(v)
 return {'retailsalesperiod':'retailsaleperiod','retailavailabilityperiod':'retailsaleperiod',
         'bestifusedbydate':'bestifusedby','bestifusedbydates':'bestifusedby',
         'bestifsoldbydate':'bestifsoldby','bestifsoldbydates':'bestifsoldby',
         'bestbydate':'bestby','bestbydates':'bestby'}.get(key,key)

def normrow(row,kind):
 r=[text(v).casefold() for v in row]
 if kind=='scopes':
  r[3]=package(r[3]);r[5]=basis(r[5])
  for col in [6,7]:
   if re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}',r[col]):r[col]=datetime.strptime(r[col],'%Y/%m/%d').date().isoformat()
 elif kind=='changes':
  r[2]=package(r[2]);change=wording(r[3])
  r[3]='added' if change in {'added','addition','add','additionalpack','additionalpacks','packadded','packsadded'} else change
 elif kind=='channels':
  r[3]=package(r[3]);r[6]=';'.join(sorted(STATES.get(x.strip().upper(),x.strip().upper()) for x in re.split(r'[;,，；]',r[6]) if x.strip()))
 return tuple(r)

def source_reference_map(input_dir):
 """Read the supplied PDF table identities, independently of Golden/reference answers.

 A row citation supports a product identity or a product/customer relationship.
 Numeric/date/code facts remain checked against the independently verified facts.
 Expansion membership is computed as the set difference of public PDF pack lists.
 """
 import fitz
 records={}
 for path in sorted((Path(input_dir)/'supplier-notices').glob('*.pdf')):
  with fitz.open(path) as document:
   for page in document:
    for table in page.find_tables().tables:
     cells=table.extract()
     if not cells or not cells[0] or text(cells[0][0])!='Ref.':continue
     for cells_row in cells[1:]:
      row=[text(c) for c in cells_row]
      ref=row[0]
      if not re.fullmatch(r'N0[1-4]-[WBP]\d{2}',ref):raise RuntimeError('Unreadable public notice row reference: '+ref)
      if ref in records:raise RuntimeError('Duplicate public notice row reference: '+ref)
      records[ref]=row[1:]
 groups={prefix:[(ref,row) for ref,row in records.items() if ref.startswith(prefix)] for prefix in ['N01-W','N01-B','N02-W','N03-P','N04-P']}
 if [len(groups[p]) for p in groups]!=[15,18,3,2,9]:raise RuntimeError('Public notice tables are incomplete; reference validation unavailable')
 mapping={'scopes':{},'changes':{},'channels':{}}
 def identity(company,brand,product,size,upc=''):
  return (text(company).casefold(),text(brand).casefold(),text(product).casefold(),package(size),text(upc).casefold())
 def add(kind,key,ref):
  mapping[kind].setdefault(key,set()).update([ref,ref[:3]])
 old=set()
 for prefix,product in [('N01-W','Organic Whole Carrots'),('N01-B','Organic Baby Carrots'),('N02-W','Organic Whole Carrots')]:
  for ref,row in groups[prefix]:
   brand,sizes=row[:2]
   for size in sizes.split(','):
    key=identity('Grimmway Farms',brand,product,size)
    add('scopes',key,ref)
    change_key=(key[1],key[2],key[3])
    if prefix=='N01-W':old.add(change_key)
    if prefix=='N02-W' and change_key not in old:add('changes',change_key,ref)
 for ref,row in groups['N03-P']:
  brand,product,size=row
  key=identity('F&S Fresh Foods',brand,product,size)
  add('scopes',key,ref);add('channels',key+('whole foods market',),ref)
 for ref,row in groups['N04-P']:
  description,brand,customer=row
  match=re.search(r'(\d+\s*(?:oz|lb))',description,re.I)
  if not match:raise RuntimeError('Public notice package size could not be read: '+ref)
  upc=re.search(r'UPC\s*(\d+)',description,re.I)
  key=identity('4Earth Farms',brand,description[:match.start()].strip(),match.group(1),upc.group(1) if upc else '')
  add('scopes',key,ref);add('channels',key+(text(customer).casefold(),),ref)
 return mapping

def supported_reference(row,kind,citation,mapping):
 key=row[:5] if kind=='scopes' else row[:3] if kind=='changes' else row[:6]
 allowed=mapping[kind].get(key,set())
 refs=[r.strip().upper() for r in re.split(r'[;,]',text(citation)) if r.strip()]
 return bool(refs) and all(ref in allowed for ref in refs)

def supported_product_identity(row,citation,mapping):
 refs=[r.strip().upper() for r in re.split(r'[;,]',text(citation)) if r.strip()]
 allowed=mapping['scopes'].get(row[:5],set())
 return bool(refs) and all(ref in allowed for ref in refs)
def similarity(actual,expected):
 a,b=Counter(actual),Counter(expected);overlap=sum((a&b).values());den=max(sum(a.values()),sum(b.values()))
 return overlap/den if den else 1,dict(matching_rows=overlap,expected_rows=sum(b.values()),submitted_rows=sum(a.values()),missing=[list(k) for k in (b-a).elements()],unexpected=[list(k) for k in (a-b).elements()])
DEFINITIONS=[('product-scope.csv','scopes',10,.60),('pack-changes.csv','changes',5,.15),('distribution-list.csv','channels',7,.25)]

def verify_registers(directory,input_dir=None):
 expected=json.loads((HERE/'reference/expected.json').read_text(encoding='utf-8'))
 input_dir=Path(input_dir) if input_dir else HERE.parent/'environment/workspace/input'
 with (input_dir/'register-fields.csv').open(encoding='utf-8-sig',newline='') as f:
  schema=list(csv.DictReader(f))
 references=source_reference_map(input_dir)
 checks=[];coverage=0
 for filename,key,n,weight in DEFINITIONS:
  try:
   wanted=[r['Column'] for r in schema if r['File']==filename]
   if len(wanted)!=n+1:raise RuntimeError('Author schema is inconsistent: '+filename)
   path=Path(directory)/filename
   if not path.is_file():raise ValueError('Missing public deliverable: '+filename)
   with path.open(encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f)
    if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)) or set(reader.fieldnames)!=set(wanted):
     raise ValueError('Missing, duplicate or unexpected public columns: '+filename)
    rows=[];reference_errors=[];semantic_review_rows=[]
    expected_rows=[normrow(r,key) for r in expected[key]]
    expected_set=set(expected_rows)
    for r in reader:
     if None in r or any(v is None for v in r.values()):raise ValueError('Malformed CSV row: '+filename)
     if not any(v.strip() for v in r.values()):continue
     normalized=normrow([r[k] for k in wanted[:n]],key)
     if key=='channels' and normalized not in expected_set and supported_product_identity(normalized,r[wanted[-1]],references):
      semantic_review_rows.append(dict(row=len(rows)+len(semantic_review_rows)+2,
          relationship=list(normalized),reference=r[wanted[-1]],
          reason='Source-supported product identity; notice-level versus named-customer meaning is owned by semantic review'))
      continue
     if not supported_reference(normalized,key,r[wanted[-1]],references):
      reference_errors.append(dict(row=len(rows)+2,reference=r[wanted[-1]],reason='Missing, unknown or unrelated supplied-notice reference'))
      # A reference failure loses this record once; no separate reference penalty.
      normalized=normalized+('__unsupported_reference__',)
     rows.append(normalized)
    score,detail=similarity(rows,expected_rows)
   checks.append(dict(id=key,weight=weight,score=score,reference_errors=reference_errors,
                      semantic_review_rows=semantic_review_rows,**detail));coverage+=weight*score
  except (ValueError,UnicodeError,csv.Error,IndexError,TypeError) as exc:
   checks.append(dict(id=key,weight=weight,score=0,error=str(exc)))
 return dict(passed=all(c['score']==1 for c in checks),measurement_complete=True,score=round(coverage,8),checks=checks,
  scope='All product, amendment and distribution rows. Communication meaning is reviewed separately; no visual score.',rollout_executed=False)

def main():
 p=argparse.ArgumentParser();p.add_argument('--submission-dir',type=Path,default=Path('/workspace/output'));p.add_argument('--report',type=Path,required=True);p.add_argument('--input',type=Path)
 a=p.parse_args()
 try:result=verify_registers(a.submission_dir,a.input)
 except Exception as exc:result=dict(passed=False,measurement_complete=False,score=None,error=str(exc))
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
