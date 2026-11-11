"""Verify the public Excel submission contract directly against source records.

No Golden cell values or private candidate CSV/JSON files are read. The legacy
canonical verifier supplies only its independently formulated optimality search.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import time

from openpyxl import load_workbook
from independent import reconstruct
from verify import prove_optimal

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = dict(record_state=.12, document_precedence=.08, coordinates=.06,
               directed_routing=.12, eligibility=.08, resource_feasibility=.13,
               objective_order=.15, investment_selection=.12,
               reconciliation=.08, spatial_evidence=.06)
TABLES = {
    '方案比较': ('plan_id status cost_wan worst_urgent worst_served sum_time_s', 'plan_id'),
    '工况结果': ('plan_id scenario_id active_orders urgent_demand served urgent_served chilled_served resource_tradeoff no_feasible_site outside_snap_limit total_s', 'plan_id scenario_id'),
    '资源核对': ('plan_id scenario_id day wave station_id open minutes_limit minutes_used cold_limit cold_used served', 'plan_id scenario_id day wave station_id'),
    '订单状态': ('order_id latest_revision state issue event_ids day wave goods urgent x_m y_m longitude latitude snap_node snap_distance_m snap_eligible access_s handling_min limit_s history_event_ids', 'order_id'),
    '分配明细': ('plan_id scenario_id order_id day wave goods urgent station_id status total_s', 'plan_id scenario_id order_id'),
}
QUALITY = dict(zip(['原始消息行数','去重后消息数','重复投递数','业务订单数','有效订单数','已撤销订单数','待核订单数'],
                   ['event_rows','unique_events','duplicate_messages','orders','active','cancelled','quarantined']))
OWNERS = {'决策摘要':'investment_selection', '数据核对':'record_state', '方案比较':'investment_selection',
          '工况结果':'reconciliation', '资源核对':'reconciliation', '订单状态':'record_state', '分配明细':'eligibility'}

def scalar(value):
    if value is None: return ''
    if isinstance(value, (datetime, date)): return value.strftime('%Y-%m-%d')
    return str(value).strip()

def number(value):
    if isinstance(value, bool) or value == '': raise ValueError('A numeric value is required')
    try: result = Decimal(str(value))
    except InvalidOperation as exc: raise ValueError('Not a number: '+str(value)) from exc
    if not result.is_finite(): raise ValueError('Nonfinite number')
    return result

def same_number(a, b, tol=0):
    if a == '' or b == '': return a == b
    return abs(number(a)-number(b)) <= Decimal(str(tol))

class WorkbookData:
    def __init__(self, path, template):
        self.book = load_workbook(path, data_only=True, read_only=True)
        self.formulas = load_workbook(path, data_only=False, read_only=True)
        self.template = load_workbook(template, data_only=False, read_only=True)
        self.issues = defaultdict(list)

    def close(self):
        for book in (self.book, self.formulas, self.template): book.close()

    def rows(self, name):
        if name not in self.book: raise ValueError('Missing required worksheet: '+name)
        sheet = self.book[name]; formula_sheet = self.formulas[name]
        normalized = lambda value: re.sub(r'\s+', '', scalar(value))
        header = [normalized(v) for v in next(sheet.iter_rows(min_row=5, max_row=5, values_only=True))]
        expected = [normalized(v) for v in next(self.template[name].iter_rows(min_row=5, max_row=5, values_only=True))]
        brief_without_heading = (name == '决策摘要' and not any(header)
            and {'推荐方案','支出与预算','关键取舍','适用范围'} <= {
                scalar(row[0]) for row in sheet.iter_rows(min_row=6, values_only=True) if row})
        columns = []
        for index, label in enumerate(expected):
            if not label: continue
            if brief_without_heading:
                columns.append(index);continue
            if header.count(label) != 1: raise ValueError(name+': missing or duplicate column '+label)
            columns.append(header.index(label))
        if name in TABLES:
            fields, keys = (s.split() for s in TABLES[name])
        else:
            fields, keys = ['label','value'], ['label']
        if len(columns) != len(fields): raise ValueError(name+': invalid public template')
        answer = {}
        cells = sheet.iter_rows(min_row=6)
        formulas = formula_sheet.iter_rows(min_row=6)
        previous_blank = False
        for index, (row, formula_row) in enumerate(zip(cells, formulas), 6):
            values = []
            for col in columns:
                cell = row[col]; expression = formula_row[col]
                if expression.data_type == 'f' and cell.value is None:
                    raise ValueError(f'{name}!{cell.coordinate}: formula has no saved result; recalculate and save')
                if cell.data_type == 'e': raise ValueError(f'{name}!{cell.coordinate}: Excel error')
                values.append(scalar(cell.value))
            if not any(values):
                previous_blank = True;continue
            if previous_blank and len(values[0]) > 24 and not any(values[1:]):
                previous_blank = False;continue
            previous_blank = False
            record = dict(zip(fields, values))
            key = tuple(record[k] for k in keys)
            if not all(key):
                self.issues[name].append(f'{name} row {index}: missing record identifier');continue
            if key in answer:
                self.issues[name].append(f'{name} row {index}: duplicate identifier {key}');continue
            answer[key] = record
        return answer

def verify_workbook(inp, workbook, template=None, ref=None):
    start = time.monotonic()
    template = template or inp/'配送方案交付模板.xlsx'
    # Source reconstruction/solver failures are infrastructure failures, not candidate mistakes.
    ref = ref or reconstruct(inp)
    checks = {k:dict(status='unmeasured', passed=None, weight=v, failures=[]) for k,v in WEIGHTS.items()}
    tables = {}; measured = set(); blocked = set(); proofs = []; structural = []
    def fail(owner, message):
        if len(checks[owner]['failures']) < 12: checks[owner]['failures'].append(str(message))
    def run(owner, fn):
        try:
            fn(); measured.add(owner)
        except (ValueError, KeyError, TypeError, IndexError, InvalidOperation) as exc:
            fail(owner, str(exc)); measured.add(owner)
        except RuntimeError as exc:
            blocked.add(owner); structural.append(dict(owner=owner, kind='measurement_incomplete', message=str(exc)))
    data = None
    try:
        data = WorkbookData(workbook, template)
        for sheet, owner in OWNERS.items():
            try:
                tables[sheet] = data.rows(sheet)
                for issue in data.issues[sheet]:
                    fail(owner,issue);structural.append(dict(owner=owner,sheet=sheet,kind='invalid_artifact',message=issue))
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                fail(owner, str(exc)); structural.append(dict(owner=owner, sheet=sheet, kind='invalid_artifact', message=str(exc)))
    finally:
        if data is not None: data.close()
    expected_orders = {(o['order_id'],):o for o in ref['canonical']}
    active = {o['order_id']:o for o in ref['canonical'] if o['state']=='active'}
    scenarios = list(ref['policy']['factors']); plans = ref['plans']; sites = ref['sites']
    groups = defaultdict(list)
    for order in active.values(): groups[order['day'],order['wave']].append(order)
    assignment_keys = {(p,s,o) for p in plans for s in scenarios for o in active}
    resource_keys = {(p,s,d,w,site['station_id']) for p in plans for s in scenarios for d,w in groups for site in sites}
    def exact_keys(rows, expected, title):
        if set(rows) != set(expected): raise ValueError(title+': missing or extra record identifiers')
    def states():
        counts = tables['数据核对']; exact_keys(counts, {(k,) for k in QUALITY}, '数据核对')
        for label, key in QUALITY.items():
            if not same_number(counts[label,]['value'], ref['quality'][key]): fail('record_state', label)
        rows = tables['订单状态']; exact_keys(rows, expected_orders, '订单状态')
        for key, expected in expected_orders.items():
            for field in ['latest_revision','state','event_ids','history_event_ids','day','wave','goods','urgent','handling_min','limit_s']:
                actual = rows[key][field]; value = expected[field]
                if field in ('event_ids','history_event_ids'): correct = sorted(actual.split(';')) == sorted(str(value).split(';'))
                elif field in ['latest_revision','urgent','handling_min','limit_s']: correct = same_number(actual,value)
                else: correct = actual == str(value)
                if not correct: fail('record_state', (key,field))
    if '数据核对' in tables and '订单状态' in tables: run('record_state', states)
    def coordinates():
        rows=tables['订单状态']; exact_keys(rows,expected_orders,'订单状态')
        for key, expected in expected_orders.items():
            for field in ['x_m','y_m','longitude','latitude','snap_node','snap_distance_m','snap_eligible','access_s']:
                actual=rows[key][field]; value=expected[field]
                correct = actual==str(value) if field=='snap_node' else same_number(actual,value,1e-6 if field not in ['snap_eligible','access_s'] else 0)
                if not correct: fail('coordinates',(key,field))
    if '订单状态' in tables and set(tables['订单状态'])==set(expected_orders): run('coordinates',coordinates)
    assignments = tables.get('分配明细')
    valid_assignment_keys = assignments is not None and set(assignments)==assignment_keys
    if assignments is not None and not valid_assignment_keys: fail('eligibility','分配明细: missing or extra record identifiers')
    unsupported_served = []
    if assignments is not None:
        unsupported_served = [key for key,row in assignments.items() if key not in assignment_keys
                              and (row['station_id'] or row['status']=='served')]
        assignments = {key:row for key,row in assignments.items() if key in assignment_keys}
    actual = defaultdict(list); totals = {}; feasible = not unsupported_served
    if unsupported_served:
        for owner in ['directed_routing','resource_feasibility','spatial_evidence']:
            fail(owner,'Offered served records are outside the verified active population: '+str(unsupported_served[:5]))
    # Only offered assignments consume resources. Missing unassigned ledger rows
    # remain a coverage error but do not prevent checking the reported allocation.
    if assignments is not None:
        for (p,s,oid), row in assignments.items():
            if row['station_id']: actual[p,s,active[oid]['day'],active[oid]['wave'],row['station_id']].append(active[oid])
        def eligibility():
            nonlocal feasible
            for (p,s,oid), row in assignments.items():
                order=active[oid]; sid=row['station_id']
                for field in ['day','wave','goods','urgent']:
                    if row[field]!=str(order[field]): fail('eligibility',(p,s,oid,'metadata',field))
                options=[ref['options'][p,s,oid,site['station_id']]['reason']=='eligible' for site in sites]
                if sid:
                    option=ref['options'].get((p,s,oid,sid))
                    if not option or option['reason']!='eligible' or row['status']!='served':
                        fail('eligibility',(p,s,oid,'ineligible assignment')); feasible=False
                else:
                    reason='resource_tradeoff' if any(options) else 'outside_snap_limit' if not order['snap_eligible'] else 'no_feasible_site'
                    if row['status']!=reason or row['total_s']!='':
                        # An unassigned order consumes no resource. A wrong reason or
                        # displayed time is owned here, not proof of an infeasible allocation.
                        fail('eligibility',(p,s,oid,'unserved classification'))
        run('eligibility',eligibility)
        def routing():
            for (p,s,oid),row in assignments.items():
                sid=row['station_id']
                if not sid: continue
                expected=ref['routes'].get((s,oid,sid))
                # Unknown stations are owned by eligibility, not an invented route measurement.
                if expected is None: blocked.add('directed_routing'); continue
                if not same_number(row['total_s'],expected['total_s']): fail('directed_routing',(p,s,oid,'complete shortest service time'))
        run('directed_routing',routing)
        def limits():
            nonlocal feasible
            for p in plans:
                for s in scenarios:
                    for (day,wave),group in groups.items():
                        chosen_all=[]
                        for site in sites:
                            sid=site['station_id']; selected=actual[p,s,day,wave,sid]; r=ref['resources'][p,s,wave][sid]
                            mins=sum(o['handling_min'] for o in selected); cold=sum(o['goods']=='chilled' for o in selected)
                            if mins>r['minutes'] or cold>r['cold'] or selected and not r['open']:
                                fail('resource_feasibility',(p,s,day,wave,sid)); feasible=False
                            chosen_all.extend((o,sid) for o in selected)
                        times=[ref['routes'][s,o['order_id'],sid]['total_s'] for o,sid in chosen_all]
                        if any(t=='' for t in times): feasible=False; continue
                        totals[p,s,day,wave]=(sum(int(o['urgent']) for o,sid in chosen_all),len(chosen_all),sum(times))
        run('resource_feasibility',limits)
        def optimality():
            if not feasible:
                fail('objective_order','A complete source-feasible optimum is not substantiated by the reported allocation.'); return
            for key,target in totals.items():
                p,s,day,wave=key
                cached=ref['optimality_cache'].get(key)
                if cached is not None:
                    if target!=cached: fail('objective_order',(key,'a better feasible allocation exists'))
                    continue
                edges={(o['order_id'],site['station_id']):ref['options'][p,s,o['order_id'],site['station_id']] for o in groups[day,wave] for site in sites if ref['options'][p,s,o['order_id'],site['station_id']]['reason']=='eligible'}
                proven,receipt=prove_optimal(groups[day,wave],sites,edges,ref['resources'][p,s,wave],target)
                proofs.append(dict(plan_id=p,scenario_id=s,day=day,wave=wave,objective=target,proof=receipt))
                if proven: ref['optimality_cache'][key]=target
                else: fail('objective_order',(key,'a better feasible allocation exists'))
        run('objective_order',optimality)
        def spatial():
            orders=tables['订单状态']
            for (p,s,oid),row in assignments.items():
                if (oid,) not in orders:
                    fail('spatial_evidence',(p,s,oid,'missing reported location record'));continue
                if row['station_id'] and (orders[oid,]['snap_node']=='' or orders[oid,]['longitude']=='' or orders[oid,]['latitude']==''):
                    fail('spatial_evidence',(p,s,oid,'assignment has no traceable location'))
            # No map or private GeoJSON file is needed: order IDs join the reported
            # point ledger to the reported assignments, including unserved demand.
        if '订单状态' in tables: run('spatial_evidence',spatial)
    def precedence():
        rows=tables['资源核对']; exact_keys(rows,resource_keys,'资源核对')
        for (p,s,day,wave,sid),row in rows.items():
            expected=ref['resources'][p,s,wave][sid]
            for col,key in [('open','open'),('minutes_limit','minutes'),('cold_limit','cold')]:
                if not same_number(row[col],expected[key]): fail('document_precedence',(p,s,day,wave,sid,col))
    if '资源核对' in tables: run('document_precedence',precedence)
    expected_summaries={}
    if assignments is not None:
        for p in plans:
            for s in scenarios:
                rows=[r for (pp,ss,oid),r in assignments.items() if (pp,ss)==(p,s)]
                counts=Counter(r['status'] for r in rows)
                for oid,order in active.items():
                    if (p,s,oid) in assignments:continue
                    options=[ref['options'][p,s,oid,site['station_id']]['reason']=='eligible' for site in sites]
                    reason='resource_tradeoff' if any(options) else 'outside_snap_limit' if not order['snap_eligible'] else 'no_feasible_site'
                    counts[reason]+=1
                expected_summaries[p,s]=dict(active_orders=len(active),urgent_demand=sum(int(o['urgent']) for o in active.values()),
                    served=counts['served'],urgent_served=sum(int(active[r['order_id']]['urgent']) for r in rows if r['status']=='served'),
                    chilled_served=sum(active[r['order_id']]['goods']=='chilled' for r in rows if r['status']=='served'),
                    resource_tradeoff=counts['resource_tradeoff'],no_feasible_site=counts['no_feasible_site'],outside_snap_limit=counts['outside_snap_limit'])
        def reconciliation():
            usage=tables['资源核对']; summary=tables['工况结果']
            exact_keys(usage,resource_keys,'资源核对'); exact_keys(summary,expected_summaries,'工况结果')
            for (p,s,day,wave,sid),row in usage.items():
                selected=actual[p,s,day,wave,sid]
                expected=dict(minutes_used=sum(o['handling_min'] for o in selected),cold_used=sum(o['goods']=='chilled' for o in selected),served=len(selected))
                for field,value in expected.items():
                    if not same_number(row[field],value): fail('reconciliation',('资源核对',p,s,day,wave,sid,field))
            for key,expected in expected_summaries.items():
                p,s=key; expected=dict(expected,total_s=sum(number(r['total_s']) for (pp,ss,oid),r in assignments.items() if (pp,ss)==key and r['status']=='served'))
                for field,value in expected.items():
                    if not same_number(summary[key][field],value): fail('reconciliation',('工况结果',key,field))
        if '资源核对' in tables and '工况结果' in tables: run('reconciliation',reconciliation)
    def investment():
        comparison=tables['方案比较']; summary=tables['工况结果']; brief=tables['决策摘要']
        exact_keys(comparison,{(p,) for p in ref['policy']['plans']},'方案比较')
        exact_keys(summary,{(p,s) for p in plans for s in scenarios},'工况结果')
        metrics={}
        for p,plan in ref['policy']['plans'].items():
            row=comparison[p,]
            if not same_number(number(row['cost_wan'])*10,plan['cost_kcny']): fail('investment_selection',(p,'amount/unit'))
            status='feasible' if p in plans else 'over_budget'
            if row['status']!=status: fail('investment_selection',(p,'budget status'))
            if p not in plans:
                if any(row[k]!='' for k in ['worst_urgent','worst_served','sum_time_s']): fail('investment_selection',(p,'over-budget metrics must be blank'))
                continue
            metrics[p]=dict(worst_urgent=min(number(summary[p,s]['urgent_served']) for s in scenarios),
                worst_served=min(number(summary[p,s]['served']) for s in scenarios),sum_time_s=sum(number(summary[p,s]['total_s']) for s in scenarios))
            for field,value in metrics[p].items():
                if not same_number(row[field],value): fail('investment_selection',(p,field))
        winner=min(plans,key=lambda p:(-metrics[p]['worst_urgent'],-metrics[p]['worst_served'],ref['policy']['plans'][p]['cost_kcny'],metrics[p]['sum_time_s'],p))
        recommendation=brief.get(('推荐方案',),{}).get('value','')
        match=re.match(r'^(P\d+)(?=$|[\s:：、，,（(])',recommendation)
        if not match or match.group(1)!=winner: fail('investment_selection','推荐方案 must start with the supported plan ID')
    if all(s in tables for s in ['方案比较','工况结果','决策摘要']): run('investment_selection',investment)
    for key,check in checks.items():
        if check['failures']: check.update(status='failed',passed=False)
        elif key in measured and key not in blocked: check.update(status='passed',passed=True)
    complete=all(c['passed'] is not None for c in checks.values())
    return dict(passed=all(c['passed'] is True for c in checks.values()),measurement_complete=complete,
        score=round(sum(c['weight'] for c in checks.values() if c['passed'] is True),6) if complete else None,
        checks=checks,structural_issues=structural,independent_proofs=proofs,
        workbook_sha256=hashlib.sha256(workbook.read_bytes()).hexdigest(),seconds=round(time.monotonic()-start,2),
        scope='Public Excel template numerical/business checks only; report meaning requires the separate text-only LLM judge. Optional sheets are not format gates.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,default=ROOT/'environment/workspace/input')
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    result=verify_workbook(args.input,args.workbook)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='independent_proofs'},ensure_ascii=True,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
