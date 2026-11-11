"""Extract financial business metrics from native observations and semantic evidence."""
import collections
import hashlib
import json
from pathlib import Path

import openpyxl
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string, range_boundaries

METHODS = ['\u76f4\u7ebf\u6cd5', '\u5e74\u6570\u603b\u548c\u6cd5', '\u53cc\u500d\u4f59\u989d\u9012\u51cf\u6cd5', '\u5de5\u4f5c\u91cf\u6cd5']
OWNERS = {
    'P01': 'Straight-line annual and monthly depreciation schedules',
    'P02': 'Sum-of-years-digits annual and monthly schedules',
    'P03': 'Double-declining-balance annual and monthly schedules',
    'P04': 'Workload quantities, keyed openings and remaining-basis caps',
    'P05': 'Asset/category/global assumptions and explicit zero precedence',
    'P06': 'Reporting cutoff, service anniversaries and lifetime balances',
    'P07': 'Month-effective departmental expense allocation',
    'P08': 'Historical expense flows on the departmental dashboard',
    'P09': 'Departmental cutoff stocks, expense totals and annual reporting links',
    'P10': 'Routine maintenance at the declared finite asset/dictionary capacity',
    'P11': 'Visible asset-input, unique master-data and reporting-period diagnoses',
    'P12': 'Visible invalid total/monthly workload diagnoses',
    'P13': 'Visible keyed-opening and transfer-input diagnoses',
    'P14': 'Preserved workbook structure, presentation and offline formulas',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values):
    if not values:
        raise RuntimeError('An owner has no measured evidence')
    return sum(values) / len(values)


def accepted(check, cutoff, asset_count):
    if check['error']:
        return False
    actual, expected = check['actual'], check['expected']
    if isinstance(expected, str):
        return actual == expected
    col, _ = coordinate_from_string(check['cell'])
    if check['owner'].startswith('method:') and col in ('H', 'J'):
        return abs(actual - expected) < 1e-9
    # Annual rounding followed by monthly rounding permits one cent per month.
    # The bound accumulates only across the actual financial aggregation span.
    units = 1
    if col == 'BC':
        units = cutoff
    elif col == 'CC':
        units = 12
    elif col in ('BD', 'BE'):
        units = 480
    elif check['owner'] in ('expense-allocation', 'dashboard', 'reconciliation'):
        units = asset_count * (cutoff if col in ('Q', 'D') else 12 if col in ('O', 'B') else 480 if col in ('E', 'F') else 1)
    if check['owner'].startswith('method:') and 11 <= column_index_from_string(col) <= 30:
        units = 2
    return abs(actual - expected) <= .01000001 * units


def extract(case, scenarios, material):
    ident = case['id']
    observed = Path(case['valid_observations'])
    atoms = collections.defaultdict(list)
    ledger, calc, fees, dashboard = material.sheetnames[2:6]
    for scenario in scenarios:
        report = json.loads((observed / scenario['id'] / 'observation.json').read_text())
        if report['phase'] != 'observed' or not report['source_unchanged'] or report['candidate_sha256'] != sha(Path(case['artifact'])):
            raise RuntimeError('Pending native evidence: ' + ident + ':' + scenario['id'])
        cutoff = next((change[2] for change in scenario['changes'] if change[:2] == [material.sheetnames[1], 'B7']), material.worksheets[1]['B7'].value)
        selected = []
        for check in report['checks']:
            col, row = coordinate_from_string(check['cell'])
            selected.append((check, row, col, accepted(check, cutoff, 13 if scenario['id'] == 'last-asset-capacity' else 12)))
        if scenario['family'] in ('baseline', 'annual-methods'):
            for index, method in enumerate(METHODS[:3], 1):
                checks = [v for v in selected if v[0]['owner'] == 'method:' + method and v[1] in scenario['business_rows']]
                if checks:
                    # Each asset is an independent requested schedule; copied empty years do not dilute it.
                    groups = collections.defaultdict(list)
                    for check, row, col, passed in checks:
                        if col not in ('H', 'I', 'J') and (check['expected'] != 0 or col in ('BC', 'BD', 'BE', 'CC')):
                            groups[row].append(passed)
                    atoms['P0' + str(index)].append({'scenario': scenario['id'], 'completion': mean([mean(v) for v in groups.values()])})
        if scenario['family'] in ('baseline', 'workload-opening', 'workload-units'):
            checks = [v[3] for v in selected if v[0]['owner'] == 'method:' + METHODS[3] and v[1] in scenario['business_rows'] and v[2] not in ('H', 'I', 'J')]
            if checks:
                atoms['P04'].append({'scenario': scenario['id'], 'completion': mean(checks)})
        if scenario['family'] in ('baseline', 'assumptions'):
            assumptions = [v[3] for v in selected if v[0]['sheet'] == calc and v[1] in scenario['business_rows'] and v[2] in ('H', 'I', 'J')]
            derived = [v[3] for v in selected if v[0]['sheet'] == calc and v[1] in scenario['business_rows'] and v[2] in ('BC', 'BD', 'BE', 'CC')]
            atoms['P05'].append({'scenario': scenario['id'], 'completion': min(mean(assumptions), mean(derived))})
        if scenario['family'] in ('baseline', 'periods'):
            checks = [v[3] for v in selected if v[0]['sheet'] == calc and v[1] in scenario['business_rows'] and v[2] in ('BC', 'BD', 'BE', 'CC')]
            atoms['P06'].append({'scenario': scenario['id'], 'completion': mean(checks)})
        if scenario['family'] in ('baseline', 'department-attribution'):
            baseline_report = json.loads((observed / 'baseline/observation.json').read_text())
            baseline_values = {(v['sheet'], v['cell']): v['expected'] for v in baseline_report['checks']}
            checks = [v[3] for v in selected if v[0]['owner'] == 'expense-allocation' and
                      ((scenario['family'] == 'baseline' and (v[0]['expected'] != 0 or not v[3])) or
                       (scenario['family'] != 'baseline' and abs(v[0]['expected'] - baseline_values[(v[0]['sheet'], v[0]['cell'])]) > .005))]
            atoms['P07'].append({'scenario': scenario['id'], 'completion': mean(checks)})
            checks = [v[3] for v in selected if v[0]['owner'] == 'dashboard' and v[1] >= 30 and v[2] == 'D'
                      and (scenario['family'] == 'baseline' or abs(v[0]['expected'] - baseline_values[(v[0]['sheet'], v[0]['cell'])]) > .005)]
            atoms['P08'].append({'scenario': scenario['id'], 'completion': mean(checks)})
        if scenario['family'] in ('baseline', 'periods'):
            checks = [v[3] for v in selected if v[0]['owner'] == 'reconciliation' or
                      (v[0]['sheet'] == dashboard and (v[1] < 30 or v[2] != 'D'))]
            atoms['P09'].append({'scenario': scenario['id'], 'completion': mean(checks)})
        if scenario['family'] in ('maintenance', 'method-change'):
            checks = [v[3] for v in selected if ((v[0]['sheet'] == calc and v[1] in scenario['business_rows'] and v[2] not in ('BH',) and column_index_from_string(v[2]) < 83) or v[0]['owner'] in ('expense-allocation', 'reconciliation')) and (v[0]['expected'] != 0 or not v[3])]
            atoms['P10'].append({'scenario': scenario['id'], 'completion': mean(checks)})
    path = Path(case['diagnostic_observations'])
    diagnostics = json.loads(path.read_text())
    if diagnostics['phase'] != 'observed' or len(diagnostics['scenarios']) != 44:
        raise RuntimeError('Pending diagnostic evidence: ' + ident)
    for scenario in diagnostics['scenarios']:
        owner = 'P12' if scenario['family'] == 'workload-inputs' else 'P13' if scenario['family'] in ('opening-inputs', 'transfer-inputs') else 'P11'
        decision = case['diagnostic_decisions'][scenario['id']]
        if decision['status'] != 'measured' or decision['completion'] not in (0,1):
            raise RuntimeError('Unresolved diagnostic evidence')
        passed, hits = decision['completion'], decision['evidence']
        atoms[owner].append({'scenario': scenario['id'], 'completion': int(passed), 'evidence': hits})
    book = openpyxl.load_workbook(case['artifact'])
    def chart_shape(sheet):
        return [(type(chart).__name__, len(chart.series)) for chart in sheet._charts]

    def chart_ref_span(formula):
        if not formula or '!' not in formula or '[' in formula or ']' in formula:
            return None
        sheet_name, cell_range = formula.rsplit('!', 1)
        if sheet_name.startswith("'") and sheet_name.endswith("'"):
            sheet_name = sheet_name[1:-1].replace("''", "'")
        if sheet_name not in book.sheetnames:
            return None
        try:
            min_col, min_row, max_col, max_row = range_boundaries(cell_range.replace('$', ''))
        except ValueError:
            return None
        if min_col > max_col or min_row > max_row:
            return None
        return (max_col - min_col + 1) * (max_row - min_row + 1)

    def chart_integrity():
        for sheet in book:
            for chart in sheet._charts:
                if not chart.series:
                    return False
                for series in chart.series:
                    values=[]; categories=[]
                    for name, target in (('val', values), ('yVal', values), ('cat', categories), ('xVal', categories)):
                        obj=getattr(series,name,None)
                        for kind in ('numRef','strRef'):
                            ref=getattr(obj,kind,None) if obj is not None else None
                            if ref is not None and getattr(ref,'f',None):target.append(chart_ref_span(ref.f))
                    if not values or not categories or any(span is None for span in values + categories):
                        return False
                    if len(set(values + categories)) != 1:
                        return False
        return True
    widths=lambda sheet:{key:(value.width,value.hidden) for key,value in sheet.column_dimensions.items()}
    style_signature=lambda sheet:[c.style_id for row in sheet.iter_rows() for c in row]
    structural = [book.sheetnames == material.sheetnames, not book.vba_archive, not book._external_links,
                  sum(c.data_type == 'f' for sheet in book for row in sheet for c in row) > 100,
                  sum(len(s._charts) for s in book) == sum(len(s._charts) for s in material)]
    structural += [set(str(m) for m in book[s.title].merged_cells.ranges) == set(str(m) for m in s.merged_cells.ranges) for s in material]
    structural += [widths(book[s.title])==widths(s) for s in material]
    structural += [style_signature(book[s.title])==style_signature(s) for s in material]
    structural += [chart_shape(book[s.title])==chart_shape(s) for s in material]
    structural += [chart_integrity()]
    atoms['P14'].append({'scenario': 'source-structure', 'completion': mean(structural)})
    completion = {owner: mean([v['completion'] for v in atoms[owner]]) for owner in OWNERS}
    book.close()
    return {'id': ident, 'completion': completion, 'evidence': dict(atoms)}
