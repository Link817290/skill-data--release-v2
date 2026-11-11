"""Authoritative input reader: business DOCX tables and revisioned order messages."""
import csv, hashlib, json, math, re
from decimal import Decimal
from collections import defaultdict
from pathlib import Path
import numpy as np
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from docx.oxml.ns import qn
from pyproj import Transformer
from pyproj.exceptions import ProjError
from scipy.spatial import cKDTree

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_csv(path,rows,fields=None):
    rows=list(rows)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def read_policy(inp):
    documents={}
    for path in (inp/'业务文件').glob('*.docx'):
        if path.name.startswith('~$'):continue
        d=Document(path);code=None
        for element in d.element.body:
            if element.tag==qn('w:p'):
                text=Paragraph(element,d).text;match=re.search(r'文号：(\S+)',text)
                if match:
                    code=match.group(1)
                    if code in documents:raise ValueError('duplicate document code: '+code)
                    documents[code]=dict(text='',tables=[],sha256=hashlib.sha256(path.read_bytes()).hexdigest(),file=path.name)
                if code:documents[code]['text']+=text+'\n'
            elif element.tag==qn('w:tbl') and code:
                table=Table(element,d)
                documents[code]['tables'].append([[c.text for c in row.cells] for row in table.rows])
    def records(code,table=0):
        rows=documents[code]['tables'][table];return [dict(zip(rows[0],row)) for row in rows[1:]]
    capacity={}
    for code in ['JW-OPS-0808','JW-OPS-0809-R2']:
        for r in records(code):capacity[r['站点']+'|'+r['波次']]=dict(minutes=int(r['处理分钟']),cold=int(r['冷链单数']),prepare_s=int(r['准备秒']),document_id=code)
    factors={r['情景']:{w:[int(r[w+'分子']),int(r[w+'分母'])] for w in ['AM','MID','PM']} for r in records('JW-RISK-0809')}
    overrides=[dict(scenario=r['情景'],station=r['站点'],wave=r['波次'],minutes=None if r['处理分钟覆盖']=='保持' else int(r['处理分钟覆盖']),cold=int(r['冷链单数覆盖'])) for r in records('JW-RISK-0809',1)]
    goods={r['货类']:dict(minutes=int(r['基础处理分钟']),limit_s=int(r['基础时限秒'])) for r in records('JW-SLA-0809')}
    params={r['参数']:int(r['值']) for r in records('JW-SLA-0809',1)}
    plans={}
    for r in records('JW-CAPEX-0809'):
        cost=int(Decimal(r['报价（万元）'])*10) if '报价（万元）' in r else int(r['成本千元'])
        pid=r['方案'];p=plans.setdefault(pid,dict(cost_kcny=cost,changes=[]))
        assert p['cost_kcny']==cost
        p['changes'].append(dict(station=r['站点'],wave=r['波次'],minutes=int(r['增加分钟']),cold=int(r['增加冷链']),open=int(r['启用'])))
    budget_match=re.search(r'预算上限为人民币([\d.]+)万元',documents['JW-CAPEX-0809']['text'])
    budget=int(Decimal(budget_match.group(1))*10) if budget_match else int(re.search(r'预算上限为 (\d+) 千元',documents['JW-CAPEX-0809']['text']).group(1))
    return dict(capacity=capacity,factors=factors,overrides=overrides,goods=goods,params=params,plans=plans,budget_kcny=budget,
                documents={k:{x:v[x] for x in ['file','sha256']} for k,v in documents.items()})

def effective_resources(policy,sites,pid,scenario,wave):
    result={}
    for site in sites:
        sid=site['station_id'];r=dict(policy['capacity'][sid+'|'+wave]);r['open']=int(site['initially_open'])
        for change in policy['plans'][pid]['changes']:
            if change['station']==sid and change['wave']==wave:
                r['minutes']+=change['minutes'];r['cold']+=change['cold'];r['open']=max(r['open'],change['open'])
        for change in policy['overrides']:
            if (change['scenario'],change['station'],change['wave'])==(scenario,sid,wave):
                if change['minutes'] is not None:r['minutes']=change['minutes']
                r['cold']=change['cold']
        result[sid]=r
    return result

def canonicalize(inp,policy):
    events=read_csv(inp/'order_events.csv');byevent=defaultdict(list)
    for e in events:byevent[e['event_id']].append(e)
    bad=set();unique=[];duplicates=0
    for eid,group in byevent.items():
        variants={json.dumps(e,sort_keys=True) for e in group}
        if len(variants)>1:bad.update(e['order_id'] for e in group)
        else:unique.append(group[0]);duplicates+=len(group)-1
    groups=defaultdict(list)
    for e in unique:groups[e['order_id']].append(e)
    allids=sorted({e['order_id'] for e in events})
    tr=Transformer.from_crs(4326,32652,always_xy=True)
    inverse=Transformer.from_crs(32652,4326,always_xy=True)
    nodes=sorted(read_csv(inp/'nodes.csv'),key=lambda n:n['node_id'])
    xy=np.array([(float(n['x_m']),float(n['y_m'])) for n in nodes]);tree=cKDTree(xy)
    normalized=[]
    for oid in allids:
        group=groups[oid];rev=max((int(e['revision']) for e in group),default=0)
        latest=[e for e in group if int(e['revision'])==rev]
        evidence=';'.join(sorted(e['event_id'] for e in latest))
        history=';'.join(sorted({e['event_id'] for e in group}))
        out=dict(order_id=oid,latest_revision=rev,state='active',issue='',event_ids=evidence,history_event_ids=history,day='',wave='',goods='',urgent='',
                 x_m='',y_m='',longitude='',latitude='',snap_node='',snap_distance_m='',snap_eligible='',access_s='',handling_min='',limit_s='')
        if oid in bad:out.update(state='quarantined',issue='event_id_conflict')
        elif len({json.dumps({k:v for k,v in e.items() if k not in ['event_id','received_at']},sort_keys=True) for e in latest})>1:
            out.update(state='quarantined',issue='revision_conflict')
        else:
            e=latest[0]
            out.update({k:e[k] for k in ['day','wave','goods','urgent']})
            if e['action']=='CANCELLED':out.update(state='cancelled',issue='cancelled')
            elif e['action']!='ACTIVE' or e['day'] not in ['2022-08-10','2022-08-11'] or e['wave'] not in ['AM','MID','PM'] or e['goods'] not in policy['goods'] or e['urgent'] not in ['0','1'] or e['axis_order'] not in ['XY','YX']:
                out.update(state='quarantined',issue='invalid_business_fields')
            elif e['coord_crs'] not in ['EPSG:4326','EPSG:32652']:
                out.update(state='quarantined',issue='unknown_crs')
            elif not e['coord_1'] or not e['coord_2']:
                out.update(state='quarantined',issue='missing_coordinates')
            else:
                try:
                    a,b=float(e['coord_1']),float(e['coord_2'])
                    if e['axis_order']=='YX':a,b=b,a
                    if not math.isfinite(a) or not math.isfinite(b):raise ValueError('nonfinite coordinates')
                    if e['coord_crs']=='EPSG:4326' and not (-180<=a<=180 and -90<=b<=90):
                        raise ValueError('longitude/latitude outside valid range')
                    x,y=tr.transform(a,b,errcheck=True) if e['coord_crs']=='EPSG:4326' else (a,b)
                    if not math.isfinite(x) or not math.isfinite(y):raise ValueError('invalid projected coordinates')
                    x,y=round(x,2),round(y,2);lon,lat=inverse.transform(x,y,errcheck=True)
                    if not all(math.isfinite(v) for v in (lon,lat)):raise ValueError('invalid inverse coordinates')
                except (ValueError,TypeError,OverflowError,ProjError):
                    out.update(state='quarantined',issue='invalid_coordinates');normalized.append(out);continue
                dist,_=tree.query([x,y]);near=tree.query_ball_point([x,y],float(dist)+1e-7)
                idx=min(near,key=lambda j:(round(math.hypot(x-xy[j,0],y-xy[j,1]),7),nodes[j]['node_id']))
                dist=math.hypot(x-xy[idx,0],y-xy[idx,1]);g=policy['goods'][e['goods']];urgent=int(e['urgent'])
                out.update(x_m=x,y_m=y,longitude=round(lon,8),latitude=round(lat,8),snap_node=nodes[idx]['node_id'],
                           snap_distance_m=round(dist,6),snap_eligible=int(dist<=policy['params']['max_snap_m']),access_s=math.ceil(dist*3.6/policy['params']['access_speed_kmh']),
                           handling_min=g['minutes']+urgent*policy['params']['urgent_extra_minutes'],
                           limit_s=min(g['limit_s'],policy['params']['urgent_limit_s']) if urgent else g['limit_s'])
        normalized.append(out)
    return normalized,dict(event_rows=len(events),unique_events=len(unique),duplicate_messages=duplicates,
        orders=len(normalized),active=sum(r['state']=='active' for r in normalized),cancelled=sum(r['state']=='cancelled' for r in normalized),
        quarantined=sum(r['state']=='quarantined' for r in normalized))
