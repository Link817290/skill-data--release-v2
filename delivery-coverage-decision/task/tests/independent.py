"""Independent evidence reconstruction; XML reader + dense snapping + sparse Dijkstra.
Does not import the submitted/reference solution or read Golden output values.
"""
import csv, hashlib, json, math, re, zipfile
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
from xml.etree import ElementTree as ET
import numpy as np
from scipy.spatial.distance import cdist
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from pyproj import Transformer
from pyproj.exceptions import ProjError

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def document_policy(inp):
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};docs={}
    for p in (inp/'业务文件').glob('*.docx'):
        if p.name.startswith('~$'):continue
        with zipfile.ZipFile(p) as z:root=ET.fromstring(z.read('word/document.xml'))
        code=None
        for item in root.find('w:body',ns):
            if item.tag.endswith('}p'):
                text=''.join(t.text or '' for t in item.findall('.//w:t',ns))
                match=re.search(r'文号：(\S+)',text)
                if match:
                    code=match.group(1)
                    if code in docs:raise ValueError('duplicate document code: '+code)
                    docs[code]=[[],'',p]
                if code:docs[code][1]+=text+'\n'
            elif item.tag.endswith('}tbl') and code:
                rows=[];previous=[]
                for row in item.findall('w:tr',ns):
                    values=[]
                    for column,cell in enumerate(row.findall('w:tc',ns)):
                        value=''.join(t.text or '' for t in cell.findall('.//w:t',ns))
                        merge=cell.find('w:tcPr/w:vMerge',ns)
                        if merge is not None and merge.get('{'+ns['w']+'}val')!='restart':
                            if column>=len(previous):raise ValueError('invalid vertical table merge')
                            value=previous[column]
                        values.append(value)
                    rows.append(values);previous=values
                docs[code][0].append([dict(zip(rows[0],r)) for r in rows[1:]])
    cap={}
    for code in ('JW-OPS-0808','JW-OPS-0809-R2'):
        for r in docs[code][0][0]:cap[r['站点']+'|'+r['波次']]={'minutes':int(r['处理分钟']),'cold':int(r['冷链单数']),'prepare_s':int(r['准备秒']),'document_id':code}
    factors={}
    for r in docs['JW-RISK-0809'][0][0]:factors[r['情景']]={w:[int(r[w+'分子']),int(r[w+'分母'])] for w in ('AM','MID','PM')}
    overrides=[]
    for r in docs['JW-RISK-0809'][0][1]:overrides.append(dict(scenario=r['情景'],station=r['站点'],wave=r['波次'],minutes=None if r['处理分钟覆盖']=='保持' else int(r['处理分钟覆盖']),cold=int(r['冷链单数覆盖'])))
    goods={r['货类']:{'minutes':int(r['基础处理分钟']),'limit_s':int(r['基础时限秒'])} for r in docs['JW-SLA-0809'][0][0]}
    params={r['参数']:int(r['值']) for r in docs['JW-SLA-0809'][0][1]}
    plans={}
    for r in docs['JW-CAPEX-0809'][0][0]:
        amount=Decimal(r['报价（万元）'])*10 if '报价（万元）' in r else Decimal(r['成本千元'])
        if amount!=amount.to_integral_value():raise ValueError('Nonintegral internal currency amount')
        plans.setdefault(r['方案'],dict(cost_kcny=int(amount),changes=[]))['changes'].append(dict(station=r['站点'],wave=r['波次'],minutes=int(r['增加分钟']),cold=int(r['增加冷链']),open=int(r['启用'])))
    budget_match=re.search(r'预算上限为人民币([\d.]+)万元',docs['JW-CAPEX-0809'][1])
    budget=int(Decimal(budget_match.group(1))*10) if budget_match else int(re.search(r'预算上限为 (\d+) 千元',docs['JW-CAPEX-0809'][1]).group(1))
    return dict(capacity=cap,factors=factors,overrides=overrides,goods=goods,params=params,plans=plans,
                budget_kcny=budget,
                documents={k:dict(file=v[2].name,sha256=hashlib.sha256(v[2].read_bytes()).hexdigest()) for k,v in docs.items()})

def resource(p,sites,plan,scenario,wave):
    answer={}
    for site in sites:
        sid=site['station_id'];base=p['capacity'][sid+'|'+wave]
        changes=[c for c in p['plans'][plan]['changes'] if c['station']==sid and c['wave']==wave]
        limits=[o for o in p['overrides'] if (o['scenario'],o['station'],o['wave'])==(scenario,sid,wave)]
        minutes=base['minutes']+sum(c['minutes'] for c in changes)
        cold=base['cold']+sum(c['cold'] for c in changes)
        for limit in limits:
            minutes=minutes if limit['minutes'] is None else limit['minutes'];cold=limit['cold']
        answer[sid]=dict(minutes=minutes,cold=cold,prepare_s=base['prepare_s'],open=max([int(site['initially_open'])]+[c['open'] for c in changes]))
    return answer

def reconstruct(inp):
    policy=document_policy(inp);events=read(inp/'order_events.csv');nodes=sorted(read(inp/'nodes.csv'),key=lambda r:r['node_id'])
    sites=read(inp/'station_locations.csv');segments=read(inp/'segments.csv');positions=np.array([[float(n['x_m']),float(n['y_m'])] for n in nodes])
    byid=defaultdict(list);badevent=set()
    for e in events:byid[e['event_id']].append(e)
    unique=[];duplicates=0
    for group in byid.values():
        if any(e!=group[0] for e in group):badevent.update(e['order_id'] for e in group)
        else:unique.append(group[0]);duplicates+=len(group)-1
    normalized=[];to_m=Transformer.from_crs(4326,32652,always_xy=True);to_ll=Transformer.from_crs(32652,4326,always_xy=True)
    business_keys=[k for k in events[0] if k not in ('event_id','received_at')]
    for oid in sorted({e['order_id'] for e in events}):
        choices=[e for e in unique if e['order_id']==oid];rev=max([int(e['revision']) for e in choices],default=0)
        newest=[e for e in choices if int(e['revision'])==rev]
        r=dict(order_id=oid,latest_revision=rev,state='active',issue='',
            event_ids=';'.join(sorted(e['event_id'] for e in newest)),
            history_event_ids=';'.join(sorted({e['event_id'] for e in choices})),
            day='',wave='',goods='',urgent='',x_m='',y_m='',longitude='',latitude='',snap_node='',snap_distance_m='',snap_eligible='',access_s='',handling_min='',limit_s='')
        if oid in badevent:r.update(state='quarantined',issue='event_id_conflict')
        elif len({tuple(e[k] for k in business_keys) for e in newest})!=1:r.update(state='quarantined',issue='revision_conflict')
        else:
            e=newest[0];r.update({k:e[k] for k in ('day','wave','goods','urgent')})
            if e['action']=='CANCELLED':r.update(state='cancelled',issue='cancelled')
            elif e['action']!='ACTIVE' or e['day'] not in ('2022-08-10','2022-08-11') or e['wave'] not in ('AM','MID','PM') or e['goods'] not in policy['goods'] or e['urgent'] not in ('0','1') or e['axis_order'] not in ('XY','YX'):
                r.update(state='quarantined',issue='invalid_business_fields')
            elif e['coord_crs'] not in ('EPSG:4326','EPSG:32652'):r.update(state='quarantined',issue='unknown_crs')
            elif e['coord_1']=='' or e['coord_2']=='':r.update(state='quarantined',issue='missing_coordinates')
            else:
                try:
                    coords=[float(e['coord_1']),float(e['coord_2'])]
                    if e['axis_order']=='YX':coords=coords[::-1]
                    if not all(np.isfinite(c) for c in coords):raise ValueError('invalid coordinate value')
                    if e['coord_crs']=='EPSG:4326':
                        if abs(coords[0])>180 or abs(coords[1])>90:raise ValueError('invalid geographic range')
                        coords=list(to_m.transform(*coords,errcheck=True))
                    if not all(np.isfinite(c) for c in coords):raise ValueError('projection failed')
                    x,y=(round(c,2) for c in coords);lon,lat=to_ll.transform(x,y,errcheck=True)
                    if not np.isfinite([lon,lat]).all():raise ValueError('inverse projection failed')
                except (ValueError,TypeError,OverflowError,ProjError):
                    r.update(state='quarantined',issue='invalid_coordinates');normalized.append(r);continue
                dist=cdist([[x,y]],positions)[0];idx=int(np.flatnonzero(np.round(dist,7)==np.round(dist.min(),7))[0]);distance=float(dist[idx])
                g=policy['goods'][e['goods']];urg=int(e['urgent'])
                r.update(x_m=x,y_m=y,longitude=round(lon,8),latitude=round(lat,8),snap_node=nodes[idx]['node_id'],
                    snap_distance_m=round(distance,6),snap_eligible=int(distance<=policy['params']['max_snap_m']),access_s=int(np.ceil(distance*3.6/policy['params']['access_speed_kmh'])),
                    handling_min=g['minutes']+urg*policy['params']['urgent_extra_minutes'],
                    limit_s=min(g['limit_s'],policy['params']['urgent_limit_s']) if urg else g['limit_s'])
        normalized.append(r)
    active=[r for r in normalized if r['state']=='active'];ix={n['node_id']:i for i,n in enumerate(nodes)}
    closure={r['segment_id'] for r in read(inp/'closure_segments.csv')};routes={};legal={}
    for scenario,factors in policy['factors'].items():
        for wave,(num,den) in factors.items():
            arcs={};witness={}
            for e in segments:
                if scenario=='CLOSURE' and e['segment_id'] in closure:continue
                value=Decimal(e['length_m'])*Decimal('3.6')/Decimal(e['speed_kmh'])*num/den
                cost=int(value.to_integral_value(rounding=ROUND_CEILING))
                directions={'F':[(e['u'],e['v'])],'T':[(e['v'],e['u'])],'B':[(e['u'],e['v']),(e['v'],e['u'])]}[e['direction']]
                for u,v in directions:
                    k=(ix[u],ix[v]);arcs[k]=min(arcs.get(k,math.inf),cost);witness[e['segment_id'],u,v]=cost
            legal[scenario,wave]=witness
            rows=[k[0] for k in arcs];cols=[k[1] for k in arcs]
            matrix=csr_matrix((list(arcs.values()),(rows,cols)),shape=(len(nodes),len(nodes)))
            d=dijkstra(matrix,directed=True,indices=[ix[s['node_id']] for s in sites])
            for o in active:
                if o['wave']!=wave:continue
                for j,s in enumerate(sites):
                    t=d[j,ix[o['snap_node']]];net='' if np.isinf(t) else int(t)
                    total='' if net=='' else net+o['access_s']+policy['capacity'][s['station_id']+'|'+wave]['prepare_s']
                    routes[scenario,o['order_id'],s['station_id']]=dict(network_s=net,total_s=total)
    options={};resources={};feasible=[pid for pid,plan in policy['plans'].items() if plan['cost_kcny']<=policy['budget_kcny']]
    for plan in feasible:
        for scenario in policy['factors']:
            for wave in ('AM','MID','PM'):resources[plan,scenario,wave]=resource(policy,sites,plan,scenario,wave)
            for o in active:
                for s in sites:
                    sid=s['station_id'];r=resources[plan,scenario,o['wave']][sid];t=routes[scenario,o['order_id'],sid]
                    checks=[(not o['snap_eligible'],'outside_snap_limit'),(not r['open'],'site_closed'),
                            (r['minutes']==0,'station_unavailable'),(o['goods']=='chilled' and r['cold']==0,'cold_unavailable'),
                            (t['network_s']=='','disconnected'),(t['total_s']!='' and t['total_s']>o['limit_s'],'over_time')]
                    options[plan,scenario,o['order_id'],sid]=dict(reason=next((label for test,label in checks if test),'eligible'),total_s=t['total_s'],limit_s=o['limit_s'])
    quality=dict(event_rows=len(events),unique_events=len(unique),duplicate_messages=duplicates,orders=len(normalized),
                 active=len(active),cancelled=sum(r['state']=='cancelled' for r in normalized),quarantined=sum(r['state']=='quarantined' for r in normalized))
    return dict(policy=policy,canonical=normalized,quality=quality,routes=routes,options=options,resources=resources,sites=sites,
                legal=legal,plans=feasible,optimality_cache={})
