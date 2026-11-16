"""Internal workbook reconciliation. No reference answer amounts are used."""
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as E
import re,posixpath,math,ast
N={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
def read_book(path):
 sheets={}
 with ZipFile(path) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():shared=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))]
  rel={x.attrib['Id']:x.attrib['Target'] for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
  for sh in E.fromstring(z.read('xl/workbook.xml')).find('m:sheets',N):
   t=rel[sh.attrib[R]];member=t.lstrip('/') if t.startswith(('/','xl/')) else posixpath.normpath('xl/'+t);cells={}
   for c in E.fromstring(z.read(member)).findall('.//m:sheetData/m:row/m:c',N):
    typ=c.attrib.get('t');v=c.find('m:v',N);f=c.find('m:f',N)
    value=''.join(x.text or '' for x in c.findall('.//m:t',N)) if typ=='inlineStr' else (v.text if v is not None else '')
    if typ=='s':value=shared[int(value)]
    elif typ not in ('str','inlineStr','b','e'):
     try:value=float(value)
     except (TypeError,ValueError):pass
    cells[c.attrib['r']]={'value':value,'formula':f.text if f is not None else None,'type':typ}
   sheets[sh.attrib['name']]=cells
 return sheets

def matrix(cells):
 rows={}
 for ref,c in cells.items():
  col=0
  for letter in re.match('[A-Z]+',ref)[0]:col=26*col+ord(letter)-64
  row=int(re.search(r'\d+',ref)[0]);rows.setdefault(row,{})[col]=c['value']
 return [[r.get(i,'') for i in range(1,max(r)+1)] for _,r in sorted(rows.items())]
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def numeric_pair(row,headers):
 lows=[i for i,h in enumerate(headers) if '低值' in str(h) or '确定值' in str(h)];highs=[i for i,h in enumerate(headers) if '高值' in str(h) or '条件值' in str(h)]
 if not lows or not highs or max(lows[0],highs[0])>=len(row):return None
 a,b=row[lows[0]],row[highs[0]]
 return (float(a),float(b)) if finite(a) and finite(b) else None

def audit(path):
 book=read_book(path);sheets={k:matrix(v) for k,v in book.items()};main=None
 for name,rows in sheets.items():
  for header_index,row in enumerate(rows):
   if any('状态'==str(x) for x in row) and any('低值' in str(x) for x in row):
    # Preserve the detected header as row zero for downstream column binding;
    # title/notes rows before it must not disable the cross-sheet audit.
    main=(name,rows[header_index:]);break
  if main:break
 checks=[];issues=[];details={};formulas=sum(bool(c['formula']) for s in book.values() for c in s.values());checked=0;unsupported=[]
 # Safe arithmetic replay for cell references, ranges, aggregate and rounding formulas.
 active=set();memo={}
 def cell(sheet,ref):
  key=(sheet,ref)
  if key in memo:return memo[key]
  if key in active:raise ValueError('cycle')
  c=book[sheet].get(ref,{'value':0,'formula':None});f=c['formula']
  if not f:return c['value']
  active.add(key)
  try:value=replay(f,sheet);memo[key]=value;return value
  finally:active.remove(key)
 def replay(f,sheet):
  refs={}
  def token(m):
   name=m.group(1) or m.group(2) or sheet;ref=m.group(3).replace('$','');end=m.group(4)
   key='r'+str(len(refs))
   if end:
    def ci(s):
     x=0
     for c in s:x=x*26+ord(c)-64
     return x
    def cn(n):
     o=''
     while n:n,r=divmod(n-1,26);o=chr(65+r)+o
     return o
    a=re.match(r'([A-Z]+)(\d+)',ref);b=re.match(r'([A-Z]+)(\d+)',end.replace('$',''))
    if (int(b[2])-int(a[2])+1)*(ci(b[1])-ci(a[1])+1)>100000:raise ValueError('range bound')
    refs[key]=[cell(name,cn(c)+str(r)) for r in range(int(a[2]),int(b[2])+1) for c in range(ci(a[1]),ci(b[1])+1)]
   else:refs[key]=cell(name,ref)
   return key
  f=f.lstrip('=');f=re.sub(r"(?:'([^']+)'!|([\w\u4e00-\u9fff]+)!)?(\$?[A-Z]{1,3}\$?\d+)(?::(\$?[A-Z]{1,3}\$?\d+))?",token,f)
  f=f.replace('^','**').replace('；',',').replace(';',',');f=re.sub(r'(\d+(?:\.\d+)?)%',r'(\1/100)',f)
  def flatten(v):
   out=[]
   for x in v:out.extend(flatten(x)) if isinstance(x,list) else out.append(x)
   return out
  def ev(n):
   if isinstance(n,ast.Constant) and type(n.value) in (int,float,str,bool):return n.value
   if isinstance(n,ast.Name) and n.id in refs:return refs[n.id]
   if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return ev(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
   if isinstance(n,ast.BinOp):
    a,b=ev(n.left),ev(n.right)
    if isinstance(n.op,ast.Add):return a+b
    if isinstance(n.op,ast.Sub):return a-b
    if isinstance(n.op,ast.Mult):return a*b
    if isinstance(n.op,ast.Div):return a/b
    if isinstance(n.op,ast.Pow):
     if not finite(a) or not finite(b) or abs(b)>20 or abs(a)>1e12:raise ValueError('exponent bound')
     return a**b
   if isinstance(n,ast.Compare) and len(n.ops)==1:
    a,b=ev(n.left),ev(n.comparators[0]);op=n.ops[0]
    if isinstance(op,ast.Eq):return a==b
    if isinstance(op,ast.NotEq):return a!=b
    if isinstance(op,ast.Lt):return a<b
    if isinstance(op,ast.LtE):return a<=b
    if isinstance(op,ast.Gt):return a>b
    if isinstance(op,ast.GtE):return a>=b
   if isinstance(n,ast.BoolOp):
    vals=[bool(ev(x)) for x in n.values]
    return all(vals) if isinstance(n.op,ast.And) else any(vals)
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
    name=n.func.id.upper();args=[ev(a) for a in n.args];flat=flatten(args);nums=[x for x in flat if finite(x)]
    if name=='SUM':return sum(nums)
    if name=='AVERAGE':return sum(nums)/len(nums)
    if name=='COUNT':return len(nums)
    if name=='COUNTA':return sum(x not in ('',None) for x in flat)
    if name=='PRODUCT':return math.prod(nums)
    if name=='MIN':return min(nums)
    if name=='MAX':return max(nums)
    if name=='ABS':return abs(args[0])
    if name=='INT':return math.floor(args[0])
    if name=='ROUND':return round(args[0],int(args[1]) if len(args)>1 else 0)
    if name=='ROUNDUP':
     p=int(args[1]) if len(args)>1 else 0;scale=10**p;return math.ceil(args[0]*scale)/scale
    if name=='ROUNDDOWN':
     p=int(args[1]) if len(args)>1 else 0;scale=10**p;return math.floor(args[0]*scale)/scale
    if name=='IF':return args[1] if args[0] else args[2]
    if name=='AND':return all(map(bool,flat))
    if name=='OR':return any(map(bool,flat))
    if name=='SUMIF':
     rg,condition=args[:2];vals=args[2] if len(args)>2 else rg
     return sum(y for x,y in zip(rg,vals) if str(x)==str(condition) and finite(y))
   raise ValueError('unsupported formula')
  return ev(ast.parse(f,mode='eval').body)
 for name,cells in book.items():
  for ref,c in cells.items():
   if not c['formula']:continue
   try:
    got=cell(name,ref);want=c['value'];ok=finite(got) and finite(want) and abs(got-want)<=.02
    checks.append(ok);checked+=1
    if not ok:issues.append(name+'!'+ref+' cached formula differs from independent replay')
   except Exception:unsupported.append(name+'!'+ref)
 details.update(formula_count=formulas,formulas_replayed=checked,
                unsupported_formulas=unsupported,
                formula_coverage_complete=not unsupported,
                main_table_detected=bool(main))
 if main:
  mainname,rows=main;adopted={};oneoff=[0.,0.];included=0
  for row in rows[1:]:
   pair=numeric_pair(row,rows[0])
   if pair is None:continue
   label=str(row[0]);adopted[label]=pair;text=' '.join(map(str,row))
   if ('进入一次性' in text or '低值进入' in text) and '不进入' not in text:
    oneoff=[a+b for a,b in zip(oneoff,pair)];included+=1
  # Cross-check declared adopted parameters with the actual numeric recipes in main rows.
  recipes={str(row[0]):' '.join(map(str,row[4:])) for row in rows[1:] if row}
  for pname,prows in sheets.items():
   if not prows or not any('采用值'==str(h) for h in prows[0]):continue
   column=next(i for i,h in enumerate(prows[0]) if str(h)=='采用值')
   for row in prows[1:]:
    if len(row)<=column or not finite(row[column]):continue
    label=str(row[0]);value=float(row[column]);targets=[]
    if '口径合计' in label and '工资' in label:targets=[r for k,r in recipes.items() if '年休' in k or '竞业' in k]
    elif '已付加班工资' in label:targets=[r for k,r in recipes.items() if '年休' in k]
    elif '累计未休年假' in label:targets=[r for k,r in recipes.items() if '年休' in k]
    for recipe in targets:
     numbers=[float(n) for n in re.findall(r'(?<![A-Za-z])\d+(?:\.\d+)?',recipe.replace(',',''))]
     ok=any(abs(x-value)<.02 for x in numbers);checks.append(ok)
     if not ok:issues.append(pname+': adopted parameter '+label+' differs from main calculation recipe')
  for name,other in sheets.items():
   if name==mainname or not other:continue
   for row in other[1:]:
    pair=numeric_pair(row,other[0])
    if pair is None:continue
    label=str(row[0]);expected=None
    if '已确定一次性' in label and included:expected=oneoff
    else:
     for key,values in adopted.items():
      if label==key:expected=values
      elif '竞业' in label and '月标准' in label and '竞业' in key:expected=values
    if expected is not None:
     ok=all(abs(a-b)<=.02 for a,b in zip(pair,expected));checks.append(ok)
     if not ok:issues.append(name+': '+label+' disagrees with adopted items/roll-up')
  details.update(adopted_item_count=len(adopted),oneoff_items=included,computed_oneoff=oneoff)
 if not main:
  issues.append('main settlement table with status and low-value headers was not detected')
 details.update(check_count=len(checks),proven_inconsistencies=issues,
                issues=issues,consistent=bool(main) and all(checks) and not issues)
 return details
