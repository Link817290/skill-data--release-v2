import argparse,csv,json,math,time
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import csr_matrix
from independent import reconstruct,read

WEIGHTS=dict(document_policy=.08,order_state=.11,coordinates=.06,directed_routes=.10,service_options=.09,
             feasible_allocation=.08,resource_limits=.11,lexicographic_optimality=.12,investment_decision=.08,
             reconciliations=.06,route_witnesses=.05,budget_sensitivity=.03,geographic_output=.03)

def finite(v):
    n=float(v)
    if not math.isfinite(n):raise ValueError('non-finite value')
    return n
def integer(v):
    n=finite(v)
    if n!=int(n):raise ValueError('integer required')
    return int(n)
def eqnum(a,b,tol=0):
    return a=='' and b=='' or a!='' and b!='' and abs(finite(a)-finite(b))<=tol

def prove_optimal(group,sites,eligible,resources,target):
    """Independent infeasibility formulation: try to improve each lexicographic level."""
    edges=[(o,s) for s in sites for o in group if (o['order_id'],s['station_id']) in eligible]
    if not edges:return tuple(target)==(0,0,0),[dict(level='empty',status=2)]
    cols=len(edges);matrix=[];lower=[];upper=[]
    for o in group:
        matrix.append([int(x['order_id']==o['order_id']) for x,s in edges]);lower.append(-np.inf);upper.append(1)
    for s in sites:
        sid=s['station_id'];r=resources[sid]
        matrix.append([int(o['handling_min']) if st['station_id']==sid else 0 for o,st in edges]);lower.append(-np.inf);upper.append(r['minutes'])
        matrix.append([int(o['goods']=='chilled') if st['station_id']==sid else 0 for o,st in edges]);lower.append(-np.inf);upper.append(r['cold'])
    base=np.asarray(matrix,dtype=float);u=np.array([int(o['urgent']) for o,s in edges]);n=np.ones(cols)
    t=np.array([eligible[o['order_id'],s['station_id']]['total_s'] for o,s in edges]);U,N,T=target
    trials=[('urgent',[u],[U+1],[np.inf]),('served',[u,n],[U,N+1],[U,np.inf]),('time',[u,n,t],[U,N,-np.inf],[U,N,T-1])]
    receipts=[]
    for name,extra,lo,hi in trials:
        constraints=LinearConstraint(csr_matrix(np.vstack([base,*extra])),np.array(lower+lo),np.array(upper+hi))
        result=milp(np.zeros(cols),integrality=np.ones(cols),bounds=Bounds(0,1),constraints=constraints,options={'time_limit':120,'mip_rel_gap':0})
        receipts.append(dict(level=name,status=int(result.status),better_solution_exists=result.status==0))
        if result.status==0:return False,receipts
        if result.status!=2:raise RuntimeError('optimality measurement incomplete: '+result.message)
    return True,receipts

def verify(inp,out,ref=None):
    start=time.monotonic();ref=ref or reconstruct(inp);failures={k:[] for k in WEIGHTS};proofs=[]
    completed=set();active_check='document_policy';interruption=None
    def bad(group,message):
        if len(failures[group])<10:failures[group].append(str(message))
    def table(file,keys,expected):
        rows=read(out/file);mapped={}
        for r in rows:
            key=tuple(r[k] for k in keys)
            if key in mapped:raise ValueError(file+': duplicate '+str(key))
            mapped[key]=r
        if set(mapped)!=set(expected):raise ValueError(file+': missing or extra keys')
        return mapped
    try:
        policy=ref['policy'];canonical=ref['canonical'];orders=[o for o in canonical if o['state']=='active'];om={o['order_id']:o for o in orders}
        sites=ref['sites'];sm={s['station_id']:s for s in sites};plans=ref['plans'];scenarios=list(policy['factors'])
        if json.loads((out/'effective_policy.json').read_text(encoding='utf-8'))!=policy:bad('document_policy','document extraction or precedence differs')
        completed.add('document_policy');active_check='order_state'
        if json.loads((out/'data_quality.json').read_text(encoding='utf-8'))!=ref['quality']:bad('order_state','quality totals')
        can=table('canonical_orders.csv',['order_id'],{(o['order_id'],) for o in canonical})
        numeric={'latest_revision','urgent','x_m','y_m','longitude','latitude','snap_distance_m','snap_eligible','access_s','handling_min','limit_s'}
        geometry={'x_m','y_m','longitude','latitude','snap_node','snap_distance_m','snap_eligible','access_s'}
        for e in canonical:
            r=can[e['order_id'],]
            for key,value in e.items():
                active_check='coordinates' if key in geometry else 'order_state'
                correct=eqnum(r[key],value,1e-6 if key in geometry else 0) if key in numeric else r[key]==str(value)
                if not correct:bad('coordinates' if key in geometry else 'order_state',(e['order_id'],key))
        completed.update(['order_state','coordinates']);active_check='directed_routes'
        rt=table('routes.csv',['scenario_id','order_id','station_id'],ref['routes'])
        for key,e in ref['routes'].items():
            if any(not eqnum(rt[key][k],v) for k,v in e.items()):bad('directed_routes',key)
        completed.add('directed_routes');active_check='service_options'
        options=table('service_options.csv',['plan_id','scenario_id','order_id','station_id'],ref['options'])
        for key,e in ref['options'].items():
            r=options[key]
            if r['reason']!=e['reason'] or any(not eqnum(r[k],e[k]) for k in ['total_s','limit_s']):bad('service_options',key)
        completed.add('service_options');active_check='feasible_allocation'
        assignment_keys={(p,s,o['order_id']) for p in plans for s in scenarios for o in orders}
        aa=table('assignments.csv',['plan_id','scenario_id','order_id'],assignment_keys)
        groups=defaultdict(list)
        for o in orders:groups[o['day'],o['wave']].append(o)
        usage_keys={(p,s,d,w,site['station_id']) for p in plans for s in scenarios for d,w in groups for site in sites}
        active_check='reconciliations'
        usage=table('resource_usage.csv',['plan_id','scenario_id','day','wave','station_id'],usage_keys)
        active_check='feasible_allocation'
        actual=defaultdict(list);objective={};expected_summaries={};resources_correct=True;allocation_correct=True
        for (p,s,oid),r in aa.items():
            o=om[oid];sid=r['station_id'];feasible=[ref['options'][p,s,oid,site['station_id']]['reason']=='eligible' for site in sites]
            if any(str(r[k])!=str(o[k]) for k in ['day','wave','goods','urgent']):bad('feasible_allocation',(p,s,oid,'metadata'));allocation_correct=False
            if sid:
                if sid not in sm or ref['options'][p,s,oid,sid]['reason']!='eligible' or r['status']!='served':
                    bad('feasible_allocation',(p,s,oid,'ineligible'));allocation_correct=False
                elif not eqnum(r['total_s'],ref['options'][p,s,oid,sid]['total_s']):bad('feasible_allocation',(p,s,oid,'time'));allocation_correct=False
                actual[p,s,o['day'],o['wave'],sid].append(o)
            else:
                reason='resource_tradeoff' if any(feasible) else 'outside_snap_limit' if not o['snap_eligible'] else 'no_feasible_site'
                if r['status']!=reason or r['total_s']!='':bad('feasible_allocation',(p,s,oid,'reason'));allocation_correct=False
        completed.add('feasible_allocation');active_check='reconciliations'
        for p in plans:
            for s in scenarios:
                for (day,wave),group in groups.items():
                    totals=[0,0,0];res=ref['resources'][p,s,wave]
                    for site in sites:
                        sid=site['station_id'];chosen=actual[p,s,day,wave,sid];r=res[sid]
                        mins=sum(o['handling_min'] for o in chosen);cold=sum(o['goods']=='chilled' for o in chosen)
                        if mins>r['minutes'] or cold>r['cold'] or chosen and not r['open']:
                            bad('resource_limits',(p,s,day,wave,sid));resources_correct=False
                        expected=dict(open=r['open'],minutes_limit=r['minutes'],minutes_used=mins,cold_limit=r['cold'],cold_used=cold,served=len(chosen))
                        if any(not eqnum(usage[p,s,day,wave,sid][k],v) for k,v in expected.items()):bad('reconciliations',('resource',p,s,day,wave,sid))
                        totals[0]+=sum(int(o['urgent']) for o in chosen);totals[1]+=len(chosen)
                        totals[2]+=sum(ref['routes'][s,o['order_id'],sid]['total_s'] for o in chosen if ref['routes'][s,o['order_id'],sid]['total_s']!='')
                    objective[p,s,day,wave]=tuple(totals)
        completed.add('resource_limits');active_check='lexicographic_optimality'
        if allocation_correct and resources_correct:
            for key,target in objective.items():
                p,s,day,wave=key
                cached=ref['optimality_cache'].get(key)
                if cached is not None:
                    if target!=cached:bad('lexicographic_optimality',(key,target,cached))
                    continue
                eligible={(o['order_id'],site['station_id']):ref['options'][p,s,o['order_id'],site['station_id']] for o in groups[day,wave] for site in sites if ref['options'][p,s,o['order_id'],site['station_id']]['reason']=='eligible'}
                proven,receipt=prove_optimal(groups[day,wave],sites,eligible,ref['resources'][p,s,wave],target)
                proofs.append(dict(plan_id=p,scenario_id=s,day=day,wave=wave,objective=target,proof=receipt))
                if proven:ref['optimality_cache'][key]=target
                else:bad('lexicographic_optimality',(key,'a better feasible solution exists'))
        else:bad('lexicographic_optimality','invalid assignment cannot certify an optimum')
        completed.add('lexicographic_optimality');active_check='reconciliations'
        summaries=table('scenario_summary.csv',['plan_id','scenario_id'],{(p,s) for p in plans for s in scenarios})
        for p in plans:
            for s in scenarios:
                rows=[r for (pp,ss,_),r in aa.items() if pp==p and ss==s];ct=Counter(r['status'] for r in rows)
                e=dict(active_orders=len(orders),urgent_demand=sum(int(o['urgent']) for o in orders),served=ct['served'],
                    urgent_served=sum(int(r['urgent']) for r in rows if r['status']=='served'),chilled_served=sum(r['goods']=='chilled' and r['status']=='served' for r in rows),
                    resource_tradeoff=ct['resource_tradeoff'],no_feasible_site=ct['no_feasible_site'],outside_snap_limit=ct['outside_snap_limit'],
                    total_s=sum(integer(r['total_s']) for r in rows if r['status']=='served'))
                expected_summaries[p,s]=e
                if any(not eqnum(summaries[p,s][k],v) for k,v in e.items()):bad('reconciliations',('scenario',p,s))
        completed.add('reconciliations');active_check='investment_decision'
        comparison=table('plan_comparison.csv',['plan_id'],{(p,) for p in policy['plans']});expected_plans={}
        for p,plan in policy['plans'].items():
            if p not in plans:e=dict(status='over_budget',cost_kcny=plan['cost_kcny'],worst_urgent='',worst_served='',sum_time_s='')
            else:e=dict(status='feasible',cost_kcny=plan['cost_kcny'],worst_urgent=min(expected_summaries[p,s]['urgent_served'] for s in scenarios),
                       worst_served=min(expected_summaries[p,s]['served'] for s in scenarios),sum_time_s=sum(expected_summaries[p,s]['total_s'] for s in scenarios))
            expected_plans[p]=dict(plan_id=p,**e)
            if comparison[p,]['status']!=e['status'] or any(not eqnum(comparison[p,][k],v) for k,v in e.items() if k!='status'):bad('investment_decision',('comparison',p))
        ranked=sorted(plans,key=lambda p:(-expected_plans[p]['worst_urgent'],-expected_plans[p]['worst_served'],expected_plans[p]['cost_kcny'],expected_plans[p]['sum_time_s'],p))
        decision=json.loads((out/'decision.json').read_text(encoding='utf-8'))
        expected_order=['maximize_worst_urgent','maximize_worst_served','minimize_cost','minimize_total_time','plan_id']
        if 'objective_order' in decision and decision['objective_order']!=expected_order:
            bad('investment_decision','explicit adopted objective order contradicts the documented investment rule')
        if decision['recommended_plan']!=ranked[0] or decision['ranking']!=ranked or decision['budget_kcny']!=policy['budget_kcny'] or decision['metrics']!=expected_plans[ranked[0]]:
            bad('investment_decision','recommendation/ranking differs from public lexicographic rule')
        completed.add('investment_decision');active_check='budget_sensitivity'
        sensitivity=table('budget_sensitivity.csv',['budget_kcny'],{(str(x),) for x in [0,75,85,105,110,120]})
        for (budget,),r in sensitivity.items():
            win=next(p for p in ranked if expected_plans[p]['cost_kcny']<=int(budget));e=expected_plans[win]
            if r['plan_id']!=win or any(not eqnum(r[k],e[k]) for k in ['worst_urgent','worst_served','cost_kcny']):bad('budget_sensitivity',budget)
        completed.add('budget_sensitivity');active_check='route_witnesses'
        selected=ranked[0];pathrows=[json.loads(line) for line in (out/'recommended_paths.jsonl').read_text(encoding='utf-8').splitlines() if line]
        seen=set();expected_path={(s,o['order_id']) for s in scenarios for o in orders if aa[selected,s,o['order_id']]['station_id']}
        for p in pathrows:
            k=p['scenario_id'],p['order_id']
            if k in seen:bad('route_witnesses','duplicate path')
            seen.add(k)
            if k not in expected_path:bad('route_witnesses','unexpected path');continue
            s,oid=k;r=aa[selected,s,oid];sid=r['station_id'];o=om[oid];ns=p['node_ids'];es=p['segment_ids']
            if p['plan_id']!=selected or p['station_id']!=sid or not ns or ns[0]!=sm[sid]['node_id'] or ns[-1]!=o['snap_node'] or len(es)!=len(ns)-1:
                bad('route_witnesses',(k,'endpoints'));continue
            costs=[ref['legal'][s,o['wave']].get((e,u,v)) for e,u,v in zip(es,ns,ns[1:])]
            if None in costs or sum(costs)!=ref['routes'][s,oid,sid]['network_s'] or not eqnum(p['network_s'],sum(costs)):
                bad('route_witnesses',(k,'illegal/nonshortest'))
        if seen!=expected_path:bad('route_witnesses','path key coverage')
        completed.add('route_witnesses');active_check='geographic_output'
        geo=json.loads((out/'recommended_coverage.geojson').read_text(encoding='utf-8'));seen=set()
        if geo['type']!='FeatureCollection':bad('geographic_output','not FeatureCollection')
        for f in geo['features']:
            prop=f['properties'];k=prop['scenario_id'],prop['order_id'];o=om.get(k[1])
            if k in seen or o is None or k[0] not in scenarios:bad('geographic_output','duplicate or unexpected feature');continue
            seen.add(k);r=aa[selected,*k]
            if f['geometry']['type']!='Point' or len(f['geometry']['coordinates'])!=2 or not all(eqnum(a,b,1e-7) for a,b in zip(f['geometry']['coordinates'],[o['longitude'],o['latitude']])):bad('geographic_output',(k,'coordinates'))
            if any(str(prop.get(key))!=str(value) for key,value in r.items()):bad('geographic_output',(k,'properties'))
        if seen!={(s,o['order_id']) for s in scenarios for o in orders}:bad('geographic_output','missing features')
        completed.add('geographic_output')
    except (OSError,ValueError,KeyError,TypeError,IndexError,csv.Error) as exc:
        interruption=dict(owner=active_check,error=type(exc).__name__,message=str(exc),kind='invalid_artifact')
        bad(active_check,'invalid/incomplete artifact: '+type(exc).__name__+': '+str(exc))
    except RuntimeError as exc:
        interruption=dict(owner=active_check,error=type(exc).__name__,message=str(exc),kind='measurement_incomplete')
    checks={k:dict(passed=False if v else True if k in completed else None,
                   status='failed' if v else 'passed' if k in completed else 'unmeasured',
                   weight=WEIGHTS[k],failures=v) for k,v in failures.items()}
    unmeasured=[k for k,v in checks.items() if v['passed'] is None]
    return dict(passed=all(v['passed'] is True for v in checks.values()),
        score=None if unmeasured or interruption else round(sum(WEIGHTS[k] for k,v in failures.items() if not v),6),
        measurement_complete=not unmeasured and interruption is None,unmeasured_checks=unmeasured,interruption=interruption,
        checks=checks,independent_proofs=proofs,seconds=round(time.monotonic()-start,2),
        scope='numeric/business/geometry verification; document presentation has a separate review')

if __name__=='__main__':
    p=argparse.ArgumentParser();root=Path(__file__).resolve().parents[1]
    p.add_argument('--input',type=Path,default=root/'environment/workspace/input');p.add_argument('--candidate',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=verify(a.input,a.candidate);a.report.parent.mkdir(exist_ok=True,parents=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='independent_proofs'},ensure_ascii=True,indent=2));raise SystemExit(0 if result['passed'] else 1)
