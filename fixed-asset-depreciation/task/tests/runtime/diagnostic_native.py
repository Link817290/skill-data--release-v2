"""Measure visible responses to invalid inputs without assigning scores."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid
import os

import openpyxl
import uno

from financial_native import digest, prop


def scenarios(names):
    _, p, l, c, _, _, o, t, _ = names
    result = []
    def add(name, family, *changes):
        result.append({'id': name, 'family': family, 'changes': list(changes)})
    for row in (5, 8):
        for key, col, value in [('cost-negative', 'G', -1), ('cost-text', 'G', 'bad cost'),
                                ('method-invalid', 'E', 'unsupported method'),
                                ('method-missing', 'E', None), ('date-missing', 'F', None),
                                ('date-text', 'F', 'not a date'), ('life-fractional', 'H', 2.5),
                                ('life-zero', 'H', 0), ('life-over-capacity', 'H', 41),
                                ('residual-negative', 'M', -.01), ('residual-one', 'M', 1),
                                ('category-unknown', 'D', 'Unconfigured category'),
                                ('department-unknown', 'J', 'Unconfigured department')]:
            add(key + '-row-' + str(row), 'asset-inputs', (l, col + str(row), value))
    add('asset-duplicate', 'master-data', (l, 'B6', 'FA-2024-001'))
    add('category-duplicate', 'master-data', (p, 'C18', '\u623f\u5c4b\u5efa\u7b51\u7269'))
    add('department-duplicate', 'master-data', (p, 'C45', '\u603b\u7ecf\u529e'))
    add('workload-total-zero', 'workload-inputs', (l, 'I8', 0))
    add('workload-total-negative', 'workload-inputs', (l, 'I8', -1))
    add('workload-negative', 'workload-inputs', (c, 'AE8', -100))
    add('workload-text', 'workload-inputs', (c, 'AE8', 'not a quantity'))
    add('opening-negative', 'opening-inputs', (o, 'C5', -1))
    add('opening-above-basis', 'opening-inputs', (o, 'C5', 500000))
    add('opening-text', 'opening-inputs', (o, 'C5', 'not an amount'))
    add('opening-duplicate', 'opening-inputs', (o, 'A7', 'FA-2024-004'), (o, 'B7', 2026), (o, 'C7', 0))
    add('opening-missing', 'opening-inputs', (o, 'A5', None), (o, 'B5', None), (o, 'C5', None))
    add('transfer-department-unknown', 'transfer-inputs', (t, 'F5', 'Unconfigured department'))
    add('transfer-duplicate', 'transfer-inputs', (t, 'A6', 'FA-2024-001'))
    add('report-month-zero', 'period-inputs', (p, 'B7', 0))
    add('report-month-thirteen', 'period-inputs', (p, 'B7', 13))
    add('report-month-fractional', 'period-inputs', (p, 'B7', 6.5))
    add('report-year-fractional', 'period-inputs', (p, 'B6', 2026.5))
    return result


def main():
    candidate, output = Path(os.environ['MX6_ARTIFACT']), Path(os.environ['MX6_NATIVE_OUTPUT']) / 'diagnostics.json'
    source = openpyxl.load_workbook(candidate)
    material = openpyxl.load_workbook(os.environ['MX6_MATERIAL'])
    names = material.sheetnames
    report = {'candidate_sha256': digest(candidate), 'phase': 'running', 'scoring_performed': False,
              'lenient_evaluation_started': False, 'scenarios': []}
    with tempfile.TemporaryDirectory(prefix='mx6-diagnostic-') as temp:
        folder = Path(temp)
        private = folder / 'candidate.xlsx'
        shutil.copy2(candidate, private)
        pipe = 'mx6diag' + uuid.uuid4().hex
        command = ['libreoffice', '-env:UserInstallation=' + (folder / 'profile').as_uri(),
                   '--headless', '--nologo', '--nodefault', '--nofirststartwizard',
                   '--accept=pipe,name=' + pipe + ';urp;StarOffice.ServiceManager']
        with (output.parent / 'office.log').open('w') as log:
            server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            document = desktop = None
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
                document = desktop.loadComponentFromURL(private.as_uri(), '_blank', 0,
                    (prop('Hidden', True), prop('ReadOnly', False), prop('MacroExecutionMode', 0)))
                if document is None:
                    raise RuntimeError('Workbook could not be opened')
                document.enableAutomaticCalculation(False)
                document.calculateAll()
                def snapshot():
                    found = {}
                    for sheet in source:
                        native = document.Sheets.getByName(sheet.title)
                        values = native.getCellRangeByPosition(0, 0, sheet.max_column - 1, sheet.max_row - 1).getDataArray()
                        for row in sheet:
                            for cell in row:
                                value = values[cell.row - 1][cell.column - 1]
                                if cell.data_type == 'f' and (isinstance(value, str) or sheet.title == names[8]):
                                    found[(sheet.title, cell.coordinate)] = value
                    return found
                base = snapshot()
                report['baseline_diagnostic_values'] = [{'sheet': k[0], 'cell': k[1], 'value': v}
                    for k, v in base.items() if v not in ('', 0)]
                def set_input(sheet, address, value):
                    cell = document.Sheets.getByName(sheet).getCellRangeByName(address)
                    if value is None:
                        cell.clearContents(23)
                        if cell.getType().value != 'EMPTY':
                            raise RuntimeError('Input did not clear')
                    elif isinstance(value, (int, float)):
                        cell.setValue(value)
                        if cell.getError() or abs(cell.getValue() - value) > 1e-8:
                            raise RuntimeError('Numeric input did not apply')
                    else:
                        cell.setString(value)
                        if cell.getString() != value:
                            raise RuntimeError('Text input did not apply')
                for scenario in scenarios(names):
                    document.setModified(False)
                    document.close(True)
                    document = desktop.loadComponentFromURL(private.as_uri(), '_blank', 0,
                        (prop('Hidden', True), prop('ReadOnly', False), prop('MacroExecutionMode', 0)))
                    document.enableAutomaticCalculation(False)
                    document.calculateAll()
                    originals = []
                    for sheet, address, value in scenario['changes']:
                        cell = document.Sheets.getByName(sheet).getCellRangeByName(address)
                        originals.append((cell, cell.getFormula()))
                        set_input(sheet, address, value)
                    document.calculateAll()
                    after = snapshot()
                    scenario['changed_outputs'] = [{'sheet': k[0], 'cell': k[1], 'before': base.get(k), 'after': v}
                        for k, v in after.items() if v != base.get(k)]
                    report['scenarios'].append(scenario)
                    for cell, formula in originals:
                        cell.setFormula(formula)
                    document.calculateAll()
                    output.write_text(json.dumps(report, indent=2) + '\n')
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
                report['source_unchanged'] = digest(candidate) == report['candidate_sha256']
                output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'phase': report['phase'], 'scenario_count': len(report['scenarios'])}), flush=True)


if __name__ == '__main__':
    main()
