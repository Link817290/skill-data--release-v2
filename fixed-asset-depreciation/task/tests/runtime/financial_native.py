"""Observe real offline workbook calculations against independent arithmetic."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.utils.datetime import to_excel
import uno

STRAIGHT = '\u76f4\u7ebf\u6cd5'
SYD = '\u5e74\u6570\u603b\u548c\u6cd5'
DDB = '\u53cc\u500d\u4f59\u989d\u9012\u51cf\u6cd5'
UOP = '\u5de5\u4f5c\u91cf\u6cd5'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prop(name, value):
    result = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
    result.Name, result.Value = name, value
    return result


def annual_plan(cost, rate, years, method):
    basis = cost * (1 - rate)
    result = []
    final_pair = None
    for year in range(1, years + 1):
        if method == STRAIGHT:
            amount = basis / years
        elif method == SYD:
            amount = basis * (years - year + 1) / (years * (years + 1) / 2)
        elif method == DDB:
            if years <= 2:
                amount = basis / years
            elif year <= years - 2:
                amount = (cost - sum(result)) * 2 / years
            else:
                if final_pair is None:
                    final_pair = (basis - sum(result)) / 2
                amount = final_pair
        else:
            amount = 0
        result.append(max(0, min(basis - sum(result), amount)))
    return result


def expected_asset(workbook, sheet_names, row):
    _, params, ledger, calc, _, _, opening_sheet, transfer_sheet, _ = sheet_names
    params, ledger, calc = workbook[params], workbook[ledger], workbook[calc]
    asset = ledger.cell(row, 2).value
    category = ledger.cell(row, 4).value
    method = ledger.cell(row, 5).value
    date = ledger.cell(row, 6).value
    cost = float(ledger.cell(row, 7).value)
    categories = {params.cell(r, 3).value: (params.cell(r, 4).value, params.cell(r, 5).value)
                  for r in range(12, 32) if params.cell(r, 3).value}
    years = int(ledger.cell(row, 8).value or categories[category][0])
    rate = ledger.cell(row, 13).value
    if rate is None:
        rate = categories[category][1]
    if rate is None:
        rate = params['B5'].value
    rate = float(rate)
    year, cutoff = int(params['B6'].value), int(params['B7'].value)
    plan = annual_plan(cost, rate, years, method)
    basis = cost * (1 - rate)
    monthly = []
    opening = 0
    if method == UOP:
        rows = [r for r in range(5, 405) if workbook[opening_sheet].cell(r, 1).value == asset
                and workbook[opening_sheet].cell(r, 2).value == year]
        if len(rows) != 1:
            raise ValueError('Source workload opening is not unique')
        opening = float(workbook[opening_sheet].cell(rows[0], 3).value)
        unit = basis / float(ledger.cell(row, 9).value)
    for month in range(1, 13):
        age = (year - date.year) * 12 + month - date.month
        if not 1 <= age <= years * 12:
            amount = 0
        elif method == UOP:
            quantity = float(calc.cell(row, 29 + 2 * month).value or 0)
            amount = min(max(0, basis - opening - sum(monthly)), unit * max(0, quantity))
        else:
            amount = plan[(age - 1) // 12] / 12
        monthly.append(amount)
    elapsed = max(0, min(years * 12, (year - date.year) * 12 + cutoff - date.month))
    if method == UOP:
        cumulative = min(basis, opening + sum(monthly[:cutoff]))
    else:
        whole, remainder = divmod(elapsed, 12)
        cumulative = sum(plan[:whole]) + (plan[whole] * remainder / 12 if remainder else 0)
        cumulative = max(0, min(basis, cumulative))
    departments = [ledger.cell(row, 10).value] * 12
    transfer = workbook[transfer_sheet]
    matches = [r for r in range(5, 205) if transfer.cell(r, 1).value == asset]
    if transfer['B2'].value == year and len(matches) == 1:
        current = departments[0]
        for month in range(1, 13):
            current = transfer.cell(matches[0], month + 2).value or current
            departments[month - 1] = current
    return {'asset': asset, 'method': method, 'cost': cost, 'rate': rate, 'years': years,
            'residual': cost * rate, 'annual_plan': plan, 'monthly': monthly,
            'ytd': sum(monthly[:cutoff]), 'annual': sum(monthly),
            'cumulative': cumulative, 'net': max(cost * rate, cost - cumulative),
            'departments': departments, 'closing_department': departments[cutoff - 1]}


def observe(candidate=Path('/input/candidate.xlsx'), material=Path('/input/material.xlsx'),
            output=Path('/out/observation.json'), scenario=None):
    report = {'started_at': datetime.now(timezone.utc).isoformat(),
              'candidate_sha256': digest(candidate), 'material_sha256': digest(material),
              'phase': 'running', 'scoring_performed': False, 'lenient_evaluation_started': False,
              'checks': [], 'input_differences': [], 'formula_errors': []}
    baseline = openpyxl.load_workbook(material, data_only=False)
    submitted = openpyxl.load_workbook(candidate, data_only=False)
    sheets = baseline.sheetnames
    report['source_sheets'] = sheets
    report['submitted_sheets'] = submitted.sheetnames
    report['formula_count_before_recalculation'] = sum(
        c.data_type == 'f' for sheet in submitted for row in sheet for c in row)
    report['external_links'] = len(submitted._external_links)
    for sheet in baseline:
        if sheet.title not in submitted.sheetnames:
            continue
        for row in sheet:
            for cell in row:
                if cell.value is not None and cell.data_type != 'f':
                    actual = submitted[sheet.title][cell.coordinate].value
                    if actual != cell.value:
                        report['input_differences'].append({'sheet': sheet.title, 'cell': cell.coordinate,
                            'expected': str(cell.value), 'actual': str(actual)})
    submitted.close()
    scenario = scenario or {'id': 'baseline', 'changes': []}
    report['scenario'] = scenario
    changes = []
    for sheet, address, value in scenario['changes']:
        decoded = datetime.fromisoformat(value['date']) if isinstance(value, dict) and 'date' in value else value
        baseline[sheet][address] = decoded
        changes.append((sheet, address, decoded))
    token = uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix='mx6-measure-') as temporary:
        folder = Path(temporary)
        editable = folder / 'candidate.xlsx'
        shutil.copy2(candidate, editable)
        report['native_editing_uses_private_copy'] = True
        pipe = 'mx6measure' + token
        command = ['libreoffice', '-env:UserInstallation=' + (folder / 'profile').as_uri(),
                   '--headless', '--nologo', '--nodefault', '--nofirststartwizard',
                   '--accept=pipe,name=' + pipe + ';urp;StarOffice.ServiceManager']
        report['office_version'] = subprocess.check_output(['libreoffice', '--version'], text=True).strip()
        with (output.parent / 'office.log').open('w') as log:
            server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            desktop = document = None
            try:
                resolver = uno.getComponentContext().ServiceManager.createInstanceWithContext(
                    'com.sun.star.bridge.UnoUrlResolver', uno.getComponentContext())
                for _ in range(150):
                    try:
                        context = resolver.resolve('uno:pipe,name=' + pipe + ';urp;StarOffice.ComponentContext')
                        desktop = context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
                        break
                    except Exception:
                        time.sleep(.2)
                if desktop is None:
                    raise RuntimeError('Native office startup failed')
                document = desktop.loadComponentFromURL(editable.as_uri(), '_blank', 0,
                    (prop('Hidden', True), prop('ReadOnly', False), prop('MacroExecutionMode', 0), prop('UpdateDocMode', 0)))
                if document is None:
                    report['phase'] = 'business_unopenable'
                    return report
                document.enableAutomaticCalculation(False)
                for sheet, address, value in changes:
                    cell = document.Sheets.getByName(sheet).getCellRangeByName(address)
                    if value is None:
                        cell.clearContents(23)
                        if cell.getType().value != 'EMPTY':
                            raise RuntimeError('Scenario input was not cleared: ' + sheet + '!' + address)
                    elif isinstance(value, datetime):
                        cell.setValue(to_excel(value, baseline.epoch))
                    elif isinstance(value, (int, float)):
                        cell.setValue(value)
                    else:
                        cell.setString(value)
                    if value is not None:
                        target = to_excel(value, baseline.epoch) if isinstance(value, datetime) else value
                        if isinstance(target, (int, float)):
                            applied = not cell.getError() and abs(cell.getValue() - target) <= 1e-9 * max(1, abs(target))
                        else:
                            applied = not cell.getError() and cell.getString() == target
                        if not applied:
                            raise RuntimeError('Scenario input did not take effect: ' + sheet + '!' + address)
                document.calculateAll()
                def numeric(sheet, address, expected, owner):
                    cell = document.Sheets.getByName(sheet).getCellRangeByName(address)
                    actual, error = cell.getValue(), cell.getError()
                    report['checks'].append({'owner': owner, 'sheet': sheet, 'cell': address,
                        'actual': actual, 'expected': expected, 'error': error,
                    'passed': not error and abs(actual - expected) < .005})
                def text_value(sheet, address, expected, owner):
                    cell = document.Sheets.getByName(sheet).getCellRangeByName(address)
                    report['checks'].append({'owner': owner, 'sheet': sheet, 'cell': address,
                        'actual': cell.getString(), 'expected': expected, 'error': cell.getError(),
                        'passed': not cell.getError() and cell.getString() == expected})
                missing = [name for name in sheets if not document.Sheets.hasByName(name)]
                report['missing_sheets'] = missing
                if missing:
                    report['phase'] = 'business_missing_sheets'
                    return report
                for sheet in document.Sheets:
                    errors = sheet.queryFormulaCells(uno.getConstantByName('com.sun.star.sheet.FormulaResult.ERROR')).getRangeAddresses()
                    report['formula_errors'].extend({'sheet': sheet.Name, 'start_col': r.StartColumn,
                        'start_row': r.StartRow, 'end_col': r.EndColumn, 'end_row': r.EndRow} for r in errors)
                params, ledger, calc, fees, dashboard = sheets[1:6]
                cutoff = int(baseline[params]['B7'].value)
                assets = {}
                for row in range(5, 205):
                    if not baseline[ledger].cell(row, 2).value:
                        continue
                    expected = expected_asset(baseline, sheets, row)
                    assets[row] = expected
                    owner = 'method:' + expected['method']
                    for prefix, key in [('H', 'rate'), ('J', 'years'), ('I', 'residual'),
                                        ('BC', 'ytd'), ('BD', 'cumulative'), ('BE', 'net'), ('CC', 'annual')]:
                        numeric(calc, prefix + str(row), expected[key], owner)
                    for month, amount in enumerate(expected['monthly'], 1):
                        numeric(calc, get_column_letter(30 + 2 * month) + str(row), amount, owner)
                        text_value(calc, get_column_letter(82 + month) + str(row),
                                   expected['departments'][month - 1], 'department-attribution')
                    text_value(calc, 'BH' + str(row), expected['closing_department'], 'department-attribution')
                    if expected['method'] != UOP:
                        for year in range(1, 41):
                            column = 10 + year if year <= 20 else 40 + year
                            amount = expected['annual_plan'][year - 1] if year <= expected['years'] else 0
                            numeric(calc, get_column_letter(column) + str(row), amount, owner)
                for source_row in range(35, 65):
                    department = baseline[params].cell(source_row, 3).value
                    if not department:
                        continue
                    target_row = source_row - 30 if source_row <= 44 else source_row - 29
                    monthly = [sum(a['monthly'][m] for a in assets.values() if a['departments'][m] == department)
                               for m in range(12)]
                    for month, amount in enumerate(monthly, 1):
                        numeric(fees, get_column_letter(month + 2) + str(target_row), amount, 'expense-allocation')
                    numeric(fees, 'Q' + str(target_row), sum(monthly[:cutoff]), 'expense-allocation')
                    numeric(fees, 'O' + str(target_row), sum(monthly), 'expense-allocation')
                numeric(fees, 'Q15', sum(a['ytd'] for a in assets.values()), 'reconciliation')
                numeric(fees, 'O15', sum(a['annual'] for a in assets.values()), 'reconciliation')
                numeric(dashboard, 'B7', sum(a['cost'] for a in assets.values()), 'dashboard')
                numeric(dashboard, 'B15', sum(a['annual'] for a in assets.values()), 'dashboard')
                for row in range(30, 40):
                    department = baseline[params].cell(row + 5, 3).value
                    if not department:
                        continue
                    closed = [a for a in assets.values() if a['closing_department'] == department]
                    for prefix, key in [('C', 'cost'), ('E', 'cumulative'), ('F', 'net')]:
                        numeric(dashboard, prefix + str(row), sum(a[key] for a in closed), 'dashboard')
                    flow = sum(a['monthly'][m] for a in assets.values() for m in range(cutoff)
                               if a['departments'][m] == department)
                    numeric(dashboard, 'D' + str(row), flow, 'dashboard')
                report['phase'] = 'observed'
            except Exception as error:
                report.update(phase='technical_failure', error_type=type(error).__name__, error=str(error))
                raise
            finally:
                if document is not None:
                    document.setModified(False)
                    document.close(True)
                if desktop is not None:
                    desktop.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.terminate()
                    server.wait(timeout=10)
                report['candidate_after_sha256'] = digest(candidate)
                report['material_after_sha256'] = digest(material)
                report['source_unchanged'] = (report['candidate_sha256'] == report['candidate_after_sha256']
                                            and report['material_sha256'] == report['material_after_sha256'])
                report['finished_at'] = datetime.now(timezone.utc).isoformat()
                report['passed_checks'] = sum(c['passed'] for c in report['checks'])
                report['check_count'] = len(report['checks'])
                output.write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps({'phase': report['phase'], 'checks': report['check_count'],
                                  'passed': report['passed_checks'], 'source_unchanged': report['source_unchanged']}), flush=True)
    baseline.close()
    return report


if __name__ == '__main__':
    observe()
