"""Read actual workbook cells and evaluate formulas without changing the submission."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from zipfile import BadZipFile
from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string
from openpyxl.utils.exceptions import InvalidFileException


def normalize_id(value, ids):
    text = str(value or '').strip().upper()
    if text.endswith('.0'):
        text = text[:-2]
    for cid in ids:
        bare = cid.split('.')[0]
        if text in {cid, bare, bare.lstrip('0')}:
            return cid
    return text


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    return str(value)


def display_metadata(number_format, header_text):
    header = str(header_text or "").lower().replace(" ", "")
    scale = (1e8 if any(token in header for token in ("cny_100m", "亿元", "人民币亿元"))
             else 1e4 if any(token in header for token in ("cny_10k", "万元", "人民币万元"))
             else 1.0)
    fmt = str(number_format or "").split(";", 1)[0]
    match = re.search(r"\.([0#]+)", fmt)
    return {"unit_scale": scale, "display_decimals": len(match.group(1)) if match else 0,
            "display_percent": "%" in fmt}


def read(path, ids, scratch):
    path, scratch = Path(path), Path(scratch)
    formulas = {}
    try:
        original = load_workbook(path, data_only=False, read_only=False)
    except PermissionError as exc:
        raise RuntimeError('Workbook input permission failure') from exc
    except (BadZipFile, InvalidFileException, ValueError, KeyError, SyntaxError) as exc:
        return {'readable': False, 'error': type(exc).__name__, 'cells': {}, 'global_cells': {}, 'row_hints': []}
    for sheet in original:
        for row in sheet:
            for cell in row:
                if cell.data_type == 'f':
                    formulas[sheet.title + '!' + cell.coordinate] = cell.value
    evaluated = path
    calculation = {'formula_count': len(formulas), 'engine': None}
    if formulas:
        if not shutil.which('soffice'):
            raise RuntimeError('Workbook calculation infrastructure: LibreOffice is required')
        scratch.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix='workbook-', dir=scratch))
        incoming, output = folder / 'input', folder / 'evaluated'
        incoming.mkdir()
        output.mkdir()
        copied = incoming / 'submission.xlsx'
        shutil.copy2(path, copied)
        command = ['soffice', '-env:UserInstallation=' + (folder / 'profile').as_uri(),
                   '--headless', '--convert-to', 'xlsx', '--outdir', str(output), str(copied)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=60)
        evaluated = output / 'submission.xlsx'
        if process.returncode or not evaluated.is_file():
            raise RuntimeError('Workbook calculation infrastructure: conversion did not produce an evaluated workbook')
        calculation.update(engine='LibreOffice Calc', command=command, exit_code=process.returncode,
                           evaluated_sha256=hashlib.sha256(evaluated.read_bytes()).hexdigest())
    book = load_workbook(evaluated, data_only=True, read_only=False)
    cells, global_cells, hints, sheets = {}, {}, [], {}
    for sheet in book:
        rows = []
        column_headers = {}
        for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 10)):
            for cell in row:
                if isinstance(cell.value, str) and cell.value.strip():
                    column_headers.setdefault(cell.column, []).append(cell.value)
        for row in sheet:
            values = {cell.column_letter: _json_value(cell.value) for cell in row if cell.value is not None}
            if not values:
                continue
            candidates = [normalize_id(value, ids) for value in values.values()
                          if not isinstance(value, bool) and isinstance(value, (str, int, float))
                          and re.fullmatch(r'\d{1,6}(?:\.0|\.[A-Za-z]{2})?', str(value).strip())]
            candidates = [cid for cid in candidates if cid in ids]
            row_record = {'row': row[0].row, 'cells': values, 'company_ids': list(dict.fromkeys(candidates))}
            rows.append(row_record)
            for cell in row:
                if cell.value is None:
                    continue
                identity = sheet.title + '!' + cell.coordinate
                metadata = display_metadata(cell.number_format, " ".join(column_headers.get(cell.column, [])))
                cells[identity] = {'value': _json_value(cell.value), 'number_format': cell.number_format,
                                   'formula': formulas.get(identity), **metadata}
                if not candidates:
                    global_cells[identity] = cells[identity]
            if candidates:
                hints.append({'sheet': sheet.title, 'row': row[0].row, 'company_ids': row_record['company_ids'],
                              'leading_cells': dict(list(values.items())[:8])})
        sheets[sheet.title] = rows
    original.close()
    book.close()
    return {'readable': True, 'artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'cells': cells, 'global_cells': global_cells, 'row_hints': hints, 'sheets': sheets, 'calculation': calculation}


def records(view, layout, ids):
    if not layout:
        return {}, [], [], {}
    sheet, header, columns = layout['sheet'], layout['header_row'], layout['columns']
    if sheet not in view['sheets'] or type(header) is not int or header < 1:
        raise ValueError('Layout does not bind an actual worksheet/header')
    if not {'company_id', 'status'} <= set(columns):
        raise ValueError('Layout must identify company and call columns')
    for letter in columns.values():
        column_index_from_string(letter)
    actual, duplicates, extra, company_cells = {}, [], [], {cid: {} for cid in ids}
    for row in view['sheets'][sheet]:
        if row['row'] <= header:
            continue
        raw_id = row['cells'].get(columns['company_id'])
        if raw_id is None:
            continue
        cid = normalize_id(raw_id, ids)
        if cid not in ids:
            extra.append(cid)
            continue
        if cid in actual:
            duplicates.append(cid)
        else:
            actual[cid] = {key: row['cells'].get(letter) for key, letter in columns.items()}
            actual[cid]['_refs'] = {key: sheet + '!' + letter + str(row['row']) for key, letter in columns.items()}
        for letter in row['cells']:
            identity = sheet + '!' + letter + str(row['row'])
            company_cells[cid][identity] = view['cells'][identity]
    for name, rows in view['sheets'].items():
        for row in rows:
            for cid in row['company_ids']:
                for letter in row['cells']:
                    identity = name + '!' + letter + str(row['row'])
                    company_cells[cid][identity] = view['cells'][identity]
    return actual, duplicates, extra, company_cells


def numeric(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    text = str(value).strip().replace(',', '')
    if text.casefold() in {'inf', '+inf', 'infinity', '+infinity', '∞'}:
        return 'INF'
    percent = text.endswith('%')
    try:
        result = float(text.rstrip('%'))
        return result / 100 if percent and math.isfinite(result) else result if math.isfinite(result) else None
    except ValueError:
        return None


def correct_number(actual, expected, cell=None):
    if expected is None:
        return actual is None or isinstance(actual, str) and not actual.strip()
    parsed = numeric(actual)
    if expected == 'INF':
        return parsed == 'INF'
    if parsed is None or parsed == 'INF':
        return False
    scale = float((cell or {}).get('unit_scale', 1.0))
    parsed *= scale
    # Accept the value's displayed decimal rounding and declared header unit; a literal integer zero is
    # not a fabricated substitute for a nonzero or unavailable financial input.
    tolerance = 1e-8 * max(1.0, abs(expected))
    if cell is not None:
        digits = int(cell.get('display_decimals', 0))
        display_step = 10 ** (-digits)
        if cell.get('display_percent'):
            display_step /= 100
        tolerance = max(tolerance, .5 * display_step * scale)
    text = str(actual).strip()
    if isinstance(actual, str) and text.endswith('%'):
        digits = len(text.rstrip('%').partition('.')[2])
        tolerance = max(tolerance, .5 * 10 ** (-digits) / 100)
    elif '.' in text and not re.search(r'[eE]', text):
        tolerance = max(tolerance, .5 * 10 ** (-len(text.partition('.')[2])))
    return abs(parsed - expected) <= tolerance + 1e-12


def literal_number_in_cells(value, references, cells):
    if value in (None, 'INF'):
        return any(cells[ref]['value'] not in (None, '') for ref in references)
    for ref in references:
        raw = cells[ref]['value']
        parsed = numeric(raw)
        scale = float(cells[ref].get('unit_scale', 1.0))
        if parsed not in (None, 'INF') and (parsed == value or parsed * scale == value):
            return True
        if not isinstance(raw, str):
            continue
        for match in re.finditer(r'(?<![A-Za-z0-9])([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(\s*%|\s*亿|\s*万)?', raw):
            scale = {'%': .01, '亿': 1e8, '万': 1e4}.get((match.group(2) or '').strip(), 1)
            if math.isclose(float(match.group(1)) * scale, value, rel_tol=1e-10, abs_tol=1e-10):
                return True
    return False


def normalized_claim_number(value, references, cells):
    if type(value) not in (int, float) or isinstance(value, bool):
        return value
    for ref in references:
        raw = numeric(cells[ref]['value'])
        scale = float(cells[ref].get('unit_scale', 1.0))
        if raw not in (None, 'INF') and math.isclose(float(value), float(raw), rel_tol=1e-10, abs_tol=1e-10):
            return float(value) * scale
    return value
