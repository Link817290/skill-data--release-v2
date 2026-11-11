"""Source-bound atomic owner measurements for strict Bench calibration."""

from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from workbook_verify import WorkbookData, QUALITY, number, same_number


GROUPS = {
    'P01_source_state': ('mean', ['N01_population_counts', 'N02_order_population', 'N04_operational_attributes']),
    'P02_event_lineage': ('identity', ['N03_revision_state_lineage']),
    'P03_coordinate_conversion': ('identity', ['N05_coordinate_conversion']),
    'P04_operational_feasibility': ('mean', ['N06_snap_and_access', 'N07_resource_rule_population',
        'N08_scoped_resource_rules', 'N09_assignment_population', 'N10_assignment_identity',
        'N11_site_eligibility', 'N12_unserved_classification', 'N13_directed_service_time',
        'N14_feasibility_and_optimality', 'N21_spatial_trace']),
    'P05_reconciliation': ('min', ['N15_resource_reconciliation', 'N16_scenario_reconciliation']),
    'P06_plan_population': ('identity', ['N17_plan_population']),
    'P07_investment_decision': ('min', ['N18_quoted_terms', 'N19_robust_plan_metrics',
        'N20_adopted_recommendation']),
}


def every(pairs, compare=lambda a, b: a == b):
    pairs = list(pairs)
    return float(bool(pairs) and all(compare(a, b) for a, b in pairs))


def aggregate(atoms, method, members):
    values = [float(atoms[member]) for member in members]
    if method == 'identity': return values[0]
    if method == 'mean': return sum(values) / len(values)
    if method == 'min': return min(values)
    raise ValueError(method)


def measure_atomic(inp: Path, workbook: Path, ref, numeric):
    expected_orders = {(o['order_id'],): o for o in ref['canonical']}
    active = {o['order_id']: o for o in ref['canonical'] if o['state'] == 'active'}
    plans = ref['plans']; scenarios = list(ref['policy']['factors']); sites = ref['sites']
    groups = defaultdict(list)
    for order in active.values(): groups[order['day'], order['wave']].append(order)
    assignment_keys = {(p, s, oid) for p in plans for s in scenarios for oid in active}
    resource_keys = {(p, s, day, wave, site['station_id']) for p in plans for s in scenarios
                     for day, wave in groups for site in sites}
    data = WorkbookData(workbook, inp/'配送方案交付模板.xlsx')
    try:
        tables = {}
        issues = []
        for sheet in ['决策摘要','数据核对','方案比较','工况结果','资源核对','订单状态','分配明细']:
            try:
                tables[sheet] = data.rows(sheet)
                issues.extend(data.issues[sheet])
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                issues.append(f'{sheet}: {type(exc).__name__}: {exc}')
    finally:
        data.close()

    atoms = {}
    counts = tables.get('数据核对', {})
    atoms['N01_population_counts'] = every(
        ((counts.get((label,), {}).get('value',''), ref['quality'][key]) for label,key in QUALITY.items()),
        same_number)
    states = tables.get('订单状态', {})
    exact_states = set(states) == set(expected_orders)
    atoms['N02_order_population'] = float(exact_states)
    comparable = set(states) & set(expected_orders)
    lineage_mismatches = sum(
        (states[key].get('latest_revision',''), states[key].get('state',''),
         sorted(states[key].get('event_ids','').split(';')),
         sorted(states[key].get('history_event_ids','').split(';'))) !=
        (str(expected_orders[key]['latest_revision']), str(expected_orders[key]['state']),
         sorted(str(expected_orders[key]['event_ids']).split(';')),
         sorted(str(expected_orders[key]['history_event_ids']).split(';')))
        for key in comparable
    ) if exact_states else len(expected_orders)
    atoms['N03_revision_state_lineage'] = 1. if lineage_mismatches == 0 else .5 if lineage_mismatches == 1 else 0.
    attribute_fields=['day','wave','goods','urgent','handling_min','limit_s']
    attribute_pairs=[(states[key].get(field,''),str(expected_orders[key][field]))
                     for key in comparable for field in attribute_fields]
    atoms['N04_operational_attributes'] = (
        sum(actual==expected for actual,expected in attribute_pairs)/len(attribute_pairs)
        if exact_states and attribute_pairs else 0.)
    atoms['N05_coordinate_conversion'] = every((
        (states[key].get(field,''), expected_orders[key][field]) for key in comparable
        for field in ['x_m','y_m','longitude','latitude']),
        lambda a,b: same_number(a,b,1e-6)) if exact_states else 0.
    snap_pairs=[]
    if exact_states:
        for key in comparable:
            expected=expected_orders[key]
            snap_pairs.append((states[key].get('snap_node',''),str(expected['snap_node'])))
            for field in ['snap_distance_m','snap_eligible','access_s']:
                snap_pairs.append((states[key].get(field,''),expected[field]))
    atoms['N06_snap_and_access'] = every(snap_pairs,
        lambda a,b: a==str(b) if isinstance(b,str) else same_number(a,b,1e-6))

    resources=tables.get('资源核对',{}); exact_resources=set(resources)==resource_keys
    atoms['N07_resource_rule_population']=float(exact_resources)
    rule_pairs=[]
    if exact_resources:
        for p,s,day,wave,sid in resource_keys:
            expected=ref['resources'][p,s,wave][sid]; record=resources[p,s,day,wave,sid]
            for field,key in [('open','open'),('minutes_limit','minutes'),('cold_limit','cold')]:
                rule_pairs.append((record[field],expected[key]))
    atoms['N08_scoped_resource_rules']=every(rule_pairs,same_number)

    assignments=tables.get('分配明细',{}); exact_assignments=set(assignments)==assignment_keys
    atoms['N09_assignment_population']=float(exact_assignments)
    metadata_ok=eligibility_ok=reasons_ok=routes_ok=exact_assignments
    actual=defaultdict(list)
    if exact_assignments:
        for (p,s,oid),record in assignments.items():
            order=active[oid]
            if any(record[field]!=str(order[field]) for field in ['day','wave','goods','urgent']): metadata_ok=False
            sid=record['station_id']
            options=[ref['options'][p,s,oid,site['station_id']]['reason']=='eligible' for site in sites]
            if sid:
                option=ref['options'].get((p,s,oid,sid))
                if not option or option['reason']!='eligible' or record['status']!='served': eligibility_ok=False
                else: actual[p,s,order['day'],order['wave'],sid].append(order)
                route=ref['routes'].get((s,oid,sid))
                if route is None or not same_number(record['total_s'],route['total_s']): routes_ok=False
            else:
                reason='resource_tradeoff' if any(options) else 'outside_snap_limit' if not order['snap_eligible'] else 'no_feasible_site'
                if record['status']!=reason or record['total_s']!='': reasons_ok=False
    atoms['N10_assignment_identity']=float(metadata_ok)
    atoms['N11_site_eligibility']=float(eligibility_ok)
    atoms['N12_unserved_classification']=float(reasons_ok)
    atoms['N13_directed_service_time']=float(routes_ok)
    atoms['N14_feasibility_and_optimality']=float(
        numeric['checks']['resource_feasibility']['passed'] is True and numeric['checks']['objective_order']['passed'] is True)

    resource_reconciliation=exact_resources and exact_assignments
    if resource_reconciliation:
        for p,s,day,wave,sid in resource_keys:
            selected=actual[p,s,day,wave,sid]
            expected={'minutes_used':sum(order['handling_min'] for order in selected),
                      'cold_used':sum(order['goods']=='chilled' for order in selected),'served':len(selected)}
            if any(not same_number(resources[p,s,day,wave,sid][field],value) for field,value in expected.items()):
                resource_reconciliation=False;break
    atoms['N15_resource_reconciliation']=float(resource_reconciliation)

    summary=tables.get('工况结果',{}); expected_summaries={}
    if exact_assignments:
        for p in plans:
            for s in scenarios:
                selected=[record for (pp,ss,oid),record in assignments.items() if (pp,ss)==(p,s)]
                counts=Counter(record['status'] for record in selected)
                expected_summaries[p,s]={'active_orders':len(active),'urgent_demand':sum(int(o['urgent']) for o in active.values()),
                    'served':counts['served'],'urgent_served':sum(int(active[r['order_id']]['urgent']) for r in selected if r['status']=='served'),
                    'chilled_served':sum(active[r['order_id']]['goods']=='chilled' for r in selected if r['status']=='served'),
                    'resource_tradeoff':counts['resource_tradeoff'],'no_feasible_site':counts['no_feasible_site'],
                    'outside_snap_limit':counts['outside_snap_limit'],
                    'total_s':sum(number(r['total_s']) for r in selected if r['status']=='served')}
    scenario_reconciliation=set(summary)==set(expected_summaries) and bool(expected_summaries)
    if scenario_reconciliation:
        scenario_reconciliation=all(same_number(summary[key][field],value) for key,expected in expected_summaries.items()
                                    for field,value in expected.items())
    atoms['N16_scenario_reconciliation']=float(scenario_reconciliation)

    comparison=tables.get('方案比较',{}); policy_plans=ref['policy']['plans']
    comparison_population=set(comparison)=={(p,) for p in policy_plans}
    atoms['N17_plan_population']=float(comparison_population)
    quoted=comparison_population; metrics={}
    if comparison_population and set(summary)=={(p,s) for p in plans for s in scenarios}:
        for p,plan in policy_plans.items():
            record=comparison[p,]
            if not same_number(number(record['cost_wan'])*10,plan['cost_kcny']): quoted=False
            status='feasible' if p in plans else 'over_budget'
            if record['status']!=status: quoted=False
            if p not in plans:
                if any(record[field]!='' for field in ['worst_urgent','worst_served','sum_time_s']): quoted=False
                continue
            metrics[p]={'worst_urgent':min(number(summary[p,s]['urgent_served']) for s in scenarios),
                'worst_served':min(number(summary[p,s]['served']) for s in scenarios),
                'sum_time_s':sum(number(summary[p,s]['total_s']) for s in scenarios)}
    else: quoted=False
    atoms['N18_quoted_terms']=float(quoted)
    robust=quoted and all(same_number(comparison[p,][field],value) for p,expected in metrics.items()
                          for field,value in expected.items())
    atoms['N19_robust_plan_metrics']=float(robust)
    recommendation=tables.get('决策摘要',{}).get(('推荐方案',),{}).get('value','')
    match=re.match(r'^(P\d+)(?=$|[\s:：、，,（(])',recommendation)
    recommendation_plan=match.group(1) if match else None
    expected_plan=json.loads((Path(__file__).resolve().parent/'reference/decision.json').read_text(
        encoding='utf-8'))['recommended_plan']
    wrong_recommendation=bool(recommendation_plan and recommendation_plan != expected_plan)
    adopted=False
    if robust and metrics:
        winner=min(plans,key=lambda p:(-metrics[p]['worst_urgent'],-metrics[p]['worst_served'],
            policy_plans[p]['cost_kcny'],metrics[p]['sum_time_s'],p))
        adopted=bool(recommendation_plan==winner)
    atoms['N20_adopted_recommendation']=float(adopted)
    atoms['N21_spatial_trace']=float(numeric['checks']['spatial_evidence']['passed'] is True)
    owners={owner:aggregate(atoms,method,members) for owner,(method,members) in GROUPS.items()}
    return {'measurement_complete': True, 'atoms': atoms, 'owners': owners,
            'metrics': {'revision_state_lineage_mismatches': lineage_mismatches,
                        'expected_recommendation': expected_plan,
                        'asserted_recommendation': recommendation_plan,
                        'wrong_recommendation': wrong_recommendation},
            'parse_issues': issues, 'group_definitions': GROUPS}
