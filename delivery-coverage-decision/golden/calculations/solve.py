import argparse, csv, json, math, time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import numpy as np
import networkx as nx
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix, csr_matrix, vstack
from domain import read_csv,write_csv,read_policy,canonicalize,effective_resources

def graph_for(inp,scenario,wave,policy):
    graph=nx.DiGraph();graph.add_nodes_from(n['node_id'] for n in read_csv(inp/'nodes.csv'))
    closed={r['segment_id'] for r in read_csv(inp/'closure_segments.csv')} if scenario=='CLOSURE' else set()
    factor=Fraction(*policy['factors'][scenario][wave])
    for e in read_csv(inp/'segments.csv'):
        if e['segment_id'] in closed:continue
        value=Fraction(e['length_m'])*Fraction(18,5)/Fraction(e['speed_kmh'])*factor
        cost=-(-value.numerator//value.denominator)
        for u,v in ([(e['u'],e['v'])] if e['direction']=='F' else [(e['v'],e['u'])] if e['direction']=='T' else [(e['u'],e['v']),(e['v'],e['u'])]):
            if not graph.has_edge(u,v) or (cost,e['segment_id'])<(graph[u][v]['weight'],graph[u][v]['segment_id']):
                graph.add_edge(u,v,weight=cost,segment_id=e['segment_id'])
    return graph

def allocate(orders,sites,resources,eligible):
    """Three certified binary optimization phases. Returns a feasible assignment and bounds."""
    variables=[(o,s) for o in orders for s in sites if (o['order_id'],s['station_id']) in eligible]
    if not variables:return {},dict(urgent=0,served=0,total_s=0,phases=[],variables=0)
    oi={o['order_id']:i for i,o in enumerate(orders)};si={s['station_id']:i for i,s in enumerate(sites)}
    nr=len(orders)+2*len(sites);rows=[];cols=[];vals=[]
    for j,(o,s) in enumerate(variables):
        rows.extend([oi[o['order_id']],len(orders)+2*si[s['station_id']]])
        cols.extend([j,j]);vals.extend([1,int(o['handling_min'])])
        if o['goods']=='chilled':rows.append(len(orders)+2*si[s['station_id']]+1);cols.append(j);vals.append(1)
    matrix=coo_matrix((vals,(rows,cols)),shape=(nr,len(variables))).tocsc()
    upper=np.array([1]*len(orders)+[v for s in sites for v in [resources[s['station_id']]['minutes'],resources[s['station_id']]['cold']]],dtype=float)
    lower=np.full(nr,-np.inf)
    urgent=np.array([int(o['urgent']) for o,s in variables],dtype=float)
    served=np.ones(len(variables));cost=np.array([eligible[o['order_id'],s['station_id']]['total_s'] for o,s in variables],dtype=float)
    certificates=[];solution=None
    for label,obj in [('urgent',-urgent),('served',-served),('time',cost)]:
        result=milp(obj,integrality=np.ones(len(variables)),bounds=Bounds(0,1),
                    constraints=LinearConstraint(matrix,lower,upper),options={'mip_rel_gap':0,'time_limit':120})
        if not result.success:raise RuntimeError(f'{label}: {result.message}')
        solution=np.rint(result.x).astype(int)
        if np.max(np.abs(solution-result.x))>1e-5:raise RuntimeError('non-integral solver result')
        value=int(round(float(obj@solution)))
        certificates.append(dict(phase=label,objective=value,dual_bound=float(result.mip_dual_bound),gap=float(result.mip_gap),status=int(result.status)))
        if abs(float(result.mip_dual_bound)-value)>1e-4:raise RuntimeError('optimality bound not closed')
        matrix=vstack([matrix,csr_matrix(obj.reshape(1,-1))],format='csc')
        lower=np.append(lower,value);upper=np.append(upper,value)
    chosen={variables[j][0]['order_id']:variables[j][1]['station_id'] for j,x in enumerate(solution) if x}
    return chosen,dict(urgent=int(urgent@solution),served=int(served@solution),total_s=int(cost@solution),phases=certificates,variables=len(variables))

def solve(inp,out):
    start=time.monotonic();out.mkdir(parents=True,exist_ok=True)
    policy=read_policy(inp);canonical,quality=canonicalize(inp,policy)
    write_csv(out/'canonical_orders.csv',canonical)
    (out/'effective_policy.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'data_quality.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
    orders=[r for r in canonical if r['state']=='active'];sites=read_csv(inp/'station_locations.csv')
    groups=defaultdict(list)
    for o in orders:groups[o['day'],o['wave']].append(o)
    distances={};routes={};graphs={};route_rows=[]
    for scenario in ['BASE','CLOSURE','FAULT']:
        for wave in ['AM','MID','PM']:
            graph=graph_for(inp,scenario,wave,policy);graphs[scenario,wave]=graph
            for s in sites:
                key=(scenario,wave,s['station_id'])
                distances[key],routes[key]=nx.single_source_dijkstra(graph,s['node_id'])
            for o in orders:
                if o['wave']!=wave:continue
                for s in sites:
                    net=distances[scenario,wave,s['station_id']].get(o['snap_node'])
                    total=None if net is None else net+o['access_s']+policy['capacity'][s['station_id']+'|'+wave]['prepare_s']
                    route_rows.append(dict(scenario_id=scenario,order_id=o['order_id'],station_id=s['station_id'],network_s='' if net is None else net,total_s='' if total is None else total))
    write_csv(out/'routes.csv',route_rows);route_lookup={(r['scenario_id'],r['order_id'],r['station_id']):r for r in route_rows}
    options=[];assignments=[];resource_rows=[];summaries=[];certificates=[];ranking=[]
    for pid,plan in sorted(policy['plans'].items()):
        if plan['cost_kcny']>policy['budget_kcny']:
            ranking.append(dict(plan_id=pid,status='over_budget',cost_kcny=plan['cost_kcny'],worst_urgent='',worst_served='',sum_time_s=''));continue
        metrics=[]
        for scenario in ['BASE','CLOSURE','FAULT']:
            scenario_assign=[]
            for (day,wave),group in sorted(groups.items()):
                resources=effective_resources(policy,sites,pid,scenario,wave);eligible={};reasons=defaultdict(list)
                for o in group:
                    for s in sites:
                        sid=s['station_id'];r=resources[sid];travel=route_lookup[scenario,o['order_id'],sid]
                        reason=('outside_snap_limit' if not o['snap_eligible'] else
                                'site_closed' if not r['open'] else 'station_unavailable' if r['minutes']==0 else
                                'cold_unavailable' if o['goods']=='chilled' and r['cold']==0 else
                                'disconnected' if travel['network_s']=='' else 'over_time' if travel['total_s']>o['limit_s'] else 'eligible')
                        item=dict(plan_id=pid,scenario_id=scenario,order_id=o['order_id'],station_id=sid,reason=reason,
                                  total_s=travel['total_s'],limit_s=o['limit_s'])
                        options.append(item);reasons[o['order_id']].append(reason)
                        if reason=='eligible':eligible[o['order_id'],sid]=item
                chosen,certificate=allocate(group,sites,resources,eligible)
                certificates.append(dict(plan_id=pid,scenario_id=scenario,day=day,wave=wave,**certificate))
                for o in group:
                    oid=o['order_id'];sid=chosen.get(oid,'')
                    if sid:status='served'
                    elif 'eligible' in reasons[oid]:status='resource_tradeoff'
                    elif not o['snap_eligible']:status='outside_snap_limit'
                    else:status='no_feasible_site'
                    row=dict(plan_id=pid,scenario_id=scenario,order_id=oid,day=day,wave=wave,goods=o['goods'],urgent=o['urgent'],
                             station_id=sid,status=status,total_s=eligible[oid,sid]['total_s'] if sid else '')
                    assignments.append(row);scenario_assign.append(row)
                for s in sites:
                    sid=s['station_id'];picked=[o for o in group if chosen.get(o['order_id'])==sid];r=resources[sid]
                    resource_rows.append(dict(plan_id=pid,scenario_id=scenario,day=day,wave=wave,station_id=sid,
                        open=r['open'],minutes_limit=r['minutes'],minutes_used=sum(o['handling_min'] for o in picked),
                        cold_limit=r['cold'],cold_used=sum(o['goods']=='chilled' for o in picked),served=len(picked)))
            summary=dict(plan_id=pid,scenario_id=scenario,active_orders=len(orders),urgent_demand=sum(int(o['urgent']) for o in orders),
                served=sum(r['status']=='served' for r in scenario_assign),urgent_served=sum(int(r['urgent']) for r in scenario_assign if r['status']=='served'),
                chilled_served=sum(r['goods']=='chilled' and r['status']=='served' for r in scenario_assign),
                resource_tradeoff=sum(r['status']=='resource_tradeoff' for r in scenario_assign),
                no_feasible_site=sum(r['status']=='no_feasible_site' for r in scenario_assign),
                outside_snap_limit=sum(r['status']=='outside_snap_limit' for r in scenario_assign),
                total_s=sum(r['total_s'] for r in scenario_assign if r['status']=='served'))
            summaries.append(summary);metrics.append(summary)
        ranking.append(dict(plan_id=pid,status='feasible',cost_kcny=plan['cost_kcny'],worst_urgent=min(r['urgent_served'] for r in metrics),
                            worst_served=min(r['served'] for r in metrics),sum_time_s=sum(r['total_s'] for r in metrics)))
        print(pid,ranking[-1],flush=True)
    rank=sorted([r for r in ranking if r['status']=='feasible'],key=lambda r:(-r['worst_urgent'],-r['worst_served'],r['cost_kcny'],r['sum_time_s'],r['plan_id']))
    decision=dict(recommended_plan=rank[0]['plan_id'],ranking=[r['plan_id'] for r in rank],budget_kcny=policy['budget_kcny'],
                  objective_order=['maximize_worst_urgent','maximize_worst_served','minimize_cost','minimize_total_time','plan_id'],metrics=rank[0])
    for name,rows in [('service_options.csv',options),('assignments.csv',assignments),('resource_usage.csv',resource_rows),('scenario_summary.csv',summaries),('plan_comparison.csv',ranking)]:write_csv(out/name,rows)
    (out/'decision.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
    (out/'optimization_certificates.json').write_text(json.dumps(certificates,indent=2),encoding='utf-8')
    om={o['order_id']:o for o in orders};path_rows=[];geo=[]
    for a in assignments:
        if a['plan_id']!=decision['recommended_plan']:continue
        o=om[a['order_id']];geo.append(dict(type='Feature',geometry=dict(type='Point',coordinates=[o['longitude'],o['latitude']]),properties=a))
        if not a['station_id']:continue
        key=(a['scenario_id'],a['wave'],a['station_id']);node_path=routes[key][o['snap_node']];g=graphs[a['scenario_id'],a['wave']]
        path_rows.append(dict(plan_id=a['plan_id'],scenario_id=a['scenario_id'],order_id=a['order_id'],station_id=a['station_id'],
            node_ids=node_path,segment_ids=[g[u][v]['segment_id'] for u,v in zip(node_path,node_path[1:])],network_s=distances[key][o['snap_node']]))
    with (out/'recommended_paths.jsonl').open('w',encoding='utf-8') as f:
        for row in path_rows:f.write(json.dumps(row)+'\n')
    (out/'recommended_coverage.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=geo)),encoding='utf-8')
    sensitivity=[]
    for budget in [0,75,85,105,110,120]:
        winner=next(r for r in rank if r['cost_kcny']<=budget)
        sensitivity.append(dict(budget_kcny=budget,plan_id=winner['plan_id'],worst_urgent=winner['worst_urgent'],worst_served=winner['worst_served'],cost_kcny=winner['cost_kcny']))
    write_csv(out/'budget_sensitivity.csv',sensitivity)
    print(json.dumps(dict(quality=quality,decision=decision,seconds=round(time.monotonic()-start,2)),ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();root=Path(__file__).resolve().parents[1]
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();solve(a.input,a.output)
