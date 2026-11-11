#!/usr/bin/env python3
"""Inspect or perturb a supplied workbook; calculate with the real Office engine."""
import argparse
from datetime import datetime, timezone
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


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')


def checked_book(path):
    with zipfile.ZipFile(path) as z:
        if len(z.namelist())>4000 or sum(i.file_size for i in z.infolist())>50000000:
            raise ValueError('Workbook exceeds inspection resource bound')
        if any('vbaproject' in n.lower() or '/externallinks/' in n.lower() for n in z.namelist()):
            raise ValueError('Macro/external-link workbook is not supported')
    w=openpyxl.load_workbook(path,data_only=False)
    for sheet in w:
        for row in sheet:
            for cell in row:
                if cell.data_type=='f' and re.search(r'(?i)\b(DDE|RTD|WEBSERVICE|HYPERLINK)\s*\(|https?://|file:|\[[^\]]+\.xlsx?\]',str(cell.value)):
                    raise ValueError('External/runtime formula is not supported')
    return w


def inspect(path):
    w=checked_book(path)
    cached=openpyxl.load_workbook(path,data_only=True)
    sheets=[]
    for s in w:
        rows=[]
        for row in s:
            for c in row:
                if c.value is not None:
                    rows.append({'cell':c.coordinate,'formula':c.value if c.data_type=='f' else None,
                        'value':None if c.data_type=='f' else c.value,'cached_value':cached[s.title][c.coordinate].value,
                        'number_format':c.number_format,'data_type':c.data_type})
        formulas=[r for r in rows if r['formula'] is not None]
        sheets.append({'name':s.title,'rows':s.max_row,'columns':s.max_column,
            'formula_count':len(formulas),'formulas_without_cached_values':sum(r['cached_value'] is None for r in formulas),
            'cells':rows})
    return {'input_sha256':sha(path),'sheets':sheets,'scope':'Observed workbook only; no correctness score'}


def recalculate(source,destination,engine):
    if source.resolve()==destination.resolve():raise ValueError('Use a separate output file; original input is preserved')
    checked_book(source)
    started=datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);result=td/'result';result.mkdir()
        command=[engine,'-env:UserInstallation='+(td/'profile').as_uri(),'--headless',
            '--convert-to','xlsx','--outdir',str(result),str(source.resolve())]
        completed=subprocess.run(command,capture_output=True,text=True,timeout=600)
        file=result/source.name
        if completed.returncode or not file.is_file():
            raise RuntimeError('Office recalculation failed: '+completed.stderr)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(file,destination)
    return {'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
        'engine':engine,'input_sha256':sha(source),'output_sha256':sha(destination),
        'exit_status':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr}


def value(book,locator):
    sheet,cell=locator.rsplit('!',1)
    if not re.fullmatch(r'[A-Za-z]+[1-9][0-9]*',cell):raise ValueError('Watch locators must name single cells')
    return book[sheet][cell].value


def scenario(args):
    changes=json.loads(args.changes.read_text());watch=json.loads(args.watch.read_text())
    if not isinstance(changes,list) or not isinstance(watch,list) or not watch:
        raise ValueError('Changes must be a list; watches must be a nonempty locator list')
    original_sha=sha(args.input)
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);base=td/'base.xlsx';changed=td/'changed.xlsx';calculated=td/'changed-calculated.xlsx'
        base_log=recalculate(args.input,base,args.engine)
        w=checked_book(args.input);observed=[]
        for change in changes:
            if set(change)!={'sheet','cell','value'}:raise ValueError('Each change needs sheet, cell and value')
            cell=w[change['sheet']][change['cell']]
            if cell.data_type=='f' and not args.allow_formula_inputs:
                raise ValueError('Formula cell selected; use --allow-formula-inputs only for a known supplied input')
            observed.append({**change,'before':cell.value});cell.value=change['value']
        w.save(changed)
        change_log=recalculate(changed,calculated,args.engine)
        before=openpyxl.load_workbook(base,data_only=True);after=openpyxl.load_workbook(calculated,data_only=True)
        results=[]
        for locator in watch:
            a,b=value(before,locator),value(after,locator)
            numeric=type(a) in (int,float) and type(b) in (int,float)
            results.append({'location':locator,'before':a,'after':b,'changed':a!=b,
                'delta':b-a if numeric else None})
    return {'scope':'Measured perturbation, not an assertion that every watched result should change',
        'input_sha256':original_sha,'original_unchanged':sha(args.input)==original_sha,
        'changes':observed,'watches':results,'recalculation_logs':[base_log,change_log]}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['inspect','recalc','scenario'])
    p.add_argument('--input',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--changes',type=Path);p.add_argument('--watch',type=Path)
    p.add_argument('--engine',default='libreoffice')
    p.add_argument('--allow-formula-inputs',action='store_true');a=p.parse_args()
    try:
        if a.report.resolve()==a.input.resolve():raise ValueError('Report cannot overwrite the input workbook')
        if a.output is not None and a.report.resolve()==a.output.resolve():
            raise ValueError('Workbook output and JSON report must use separate paths')
        if a.action=='inspect':r=inspect(a.input)
        elif a.action=='recalc':
            if a.output is None:raise ValueError('--output is required for recalc')
            r=recalculate(a.input,a.output,a.engine)
        else:
            if a.changes is None or a.watch is None:raise ValueError('--changes and --watch are required for scenario')
            r=scenario(a)
        write(a.report,{'status':'measured',**r})
    except Exception as e:
        if a.report.resolve()!=a.input.resolve():write(a.report,{'status':'error','error_type':type(e).__name__,'error':str(e)})
        p.exit(2,str(e)+'\n')
