#!/usr/bin/env python3
"""Generic workbook inspection and paired native recalculation measurements."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

import openpyxl


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_report(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str, allow_nan=False)
        stream.write('\n')


def load_book(path, data_only=False):
    with zipfile.ZipFile(path) as archive:
        if any('vbaproject' in name.lower() or '/externallinks/' in name.lower()
               for name in archive.namelist()):
            raise ValueError('This helper supports local XLSX models without macros or external links')
    return openpyxl.load_workbook(path, data_only=data_only)


def locate(book, locator):
    sheet, address = locator.rsplit('!', 1)
    if not re.fullmatch(r'\$?[A-Za-z]+\$?[1-9][0-9]*', address):
        raise ValueError('A locator must identify one cell')
    return book[sheet][address]


def inspect(path):
    formulas, cached = load_book(path), load_book(path, data_only=True)
    sheets = []
    for sheet in formulas:
        cells = []
        for row in sheet:
            for cell in row:
                if cell.value is None:
                    continue
                cells.append({'cell':cell.coordinate,'data_type':cell.data_type,
                              'formula':cell.value if cell.data_type=='f' else None,
                              'input_value':None if cell.data_type=='f' else cell.value,
                              'cached_value':cached[sheet.title][cell.coordinate].value,
                              'number_format':cell.number_format})
        sheets.append({'name':sheet.title,'rows':sheet.max_row,'columns':sheet.max_column,
                       'formula_count':sum(c['formula'] is not None for c in cells),'cells':cells})
    return {'input_sha256':sha(path),'sheets':sheets}


def errors(path):
    book = load_book(path, data_only=True)
    return [{'sheet':sheet.title,'cell':cell.coordinate,'error':cell.value}
            for sheet in book for row in sheet for cell in row if cell.data_type=='e']


def recalculate(source, destination, engine):
    if source.resolve()==destination.resolve() or destination.exists():
        raise ValueError('Recalculation requires a new output path distinct from the source')
    load_book(source)
    original_sha = sha(source)
    with tempfile.TemporaryDirectory(prefix='workbook-measure-') as directory:
        directory = Path(directory)
        private = directory/'input.xlsx'
        shutil.copyfile(source, private)
        result = directory/'result'
        result.mkdir()
        command = [engine,'-env:UserInstallation='+(directory/'profile').as_uri(),
                   '--headless','--nologo','--nodefault','--nofirststartwizard',
                   '--convert-to','xlsx','--outdir',str(result),str(private)]
        process = subprocess.run(command,capture_output=True,text=True,timeout=120)
        calculated = result/private.name
        if process.returncode or not calculated.is_file():
            raise RuntimeError('Native calculation failed: '+process.stdout+process.stderr)
        formula_errors = errors(calculated)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with calculated.open('rb') as incoming, destination.open('xb') as outgoing:
            shutil.copyfileobj(incoming,outgoing)
    unchanged = sha(source)==original_sha
    if not unchanged:
        raise RuntimeError('Source workbook changed during measurement')
    return {'engine':engine,'input_sha256':original_sha,'output_sha256':sha(destination),
            'original_unchanged':unchanged,'formula_errors':formula_errors,
            'exit_status':process.returncode,'stdout':process.stdout,'stderr':process.stderr}


def scenario(args):
    changes = json.loads(args.changes.read_text(encoding='utf-8'))
    watches = json.loads(args.watch.read_text(encoding='utf-8'))
    if not isinstance(changes,list) or not isinstance(watches,list) or not watches:
        raise ValueError('Changes must be a list and watches a nonempty list')
    original_sha = sha(args.input)
    book = load_book(args.input)
    for locator in watches:
        locate(book,locator)
    mutations = []
    for change in changes:
        if not isinstance(change,dict) or set(change)!={'sheet','cell','value'}:
            raise ValueError('Each input change needs sheet, cell and value')
        cell = locate(book,change['sheet']+'!'+change['cell'])
        value = change['value']
        if cell.data_type=='f' or isinstance(cell,openpyxl.cell.cell.MergedCell):
            raise ValueError('Changes must target editable inputs, not formulas or merged placeholders')
        if isinstance(value,(dict,list)) or isinstance(value,str) and value.startswith('='):
            raise ValueError('Changes must contain literal input values')
        mutations.append({**change,'before':cell.value})
        cell.value = value
    with tempfile.TemporaryDirectory(prefix='workbook-pair-') as directory:
        directory = Path(directory)
        changed, base, calculated = (directory/name for name in ['changed.xlsx','base.xlsx','calculated.xlsx'])
        book.save(changed)
        base_log = recalculate(args.input,base,args.engine)
        changed_log = recalculate(changed,calculated,args.engine)
        before, after = load_book(base,True), load_book(calculated,True)
        observations = []
        for locator in watches:
            a, b = locate(before,locator), locate(after,locator)
            numeric = type(a.value) in (int,float) and type(b.value) in (int,float)
            observations.append({'location':locator,'before':a.value,'after':b.value,
                                 'before_type':a.data_type,'after_type':b.data_type,
                                 'changed':a.value!=b.value,
                                 'delta':b.value-a.value if numeric else None})
    unchanged = sha(args.input)==original_sha
    if not unchanged:
        raise RuntimeError('Source workbook changed during measurement')
    return {'input_sha256':original_sha,'original_unchanged':unchanged,'changes':mutations,
            'watches':observations,'recalculation_logs':[base_log,changed_log]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['inspect','recalc','scenario'])
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--changes',type=Path)
    parser.add_argument('--watch',type=Path)
    parser.add_argument('--engine',default='libreoffice')
    args = parser.parse_args()
    sources = [p.resolve() for p in [args.input,args.changes,args.watch] if p is not None]
    if args.report.exists() or args.report.resolve() in sources:
        parser.error('Use a new report path distinct from all input files')
    if args.output is not None and (args.output.resolve() in sources or args.output.resolve()==args.report.resolve()):
        parser.error('Output must be distinct from inputs and report')
    try:
        if args.action=='inspect':
            result = inspect(args.input)
        elif args.action=='recalc':
            if args.output is None:
                raise ValueError('--output is required for recalc')
            result = recalculate(args.input,args.output,args.engine)
        else:
            if args.changes is None or args.watch is None:
                raise ValueError('--changes and --watch are required for scenario')
            result = scenario(args)
        write_report(args.report,{'status':'measured','scope':'Observations only; no correctness score',**result})
    except Exception as exc:
        write_report(args.report,{'status':'error','error_type':type(exc).__name__,'error':str(exc)})
        parser.exit(2,str(exc)+'\n')


if __name__=='__main__':
    main()
