"""Native supplementary source-input, dashboard and control observations."""
from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid
import os

import openpyxl
from openpyxl.utils.datetime import to_excel
import uno

from financial_native import digest, expected_asset, prop


@contextmanager
def office(folder):
    pipe = 'mx6source' + uuid.uuid4().hex
    command = ['libreoffice','-env:UserInstallation=' + (folder / 'profile').as_uri(),
               '--headless','--nologo','--nodefault','--nofirststartwizard',
               '--accept=pipe,name=' + pipe + ';urp;StarOffice.ServiceManager']
    server = subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    desktop = None
    try:
        resolver = uno.getComponentContext().ServiceManager.createInstanceWithContext(
            'com.sun.star.bridge.UnoUrlResolver',uno.getComponentContext())
        for _ in range(150):
            try:
                context = resolver.resolve('uno:pipe,name=' + pipe + ';urp;StarOffice.ComponentContext')
                desktop = context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',context)
                break
            except Exception:
                time.sleep(.2)
        if desktop is None:
            raise RuntimeError('Native office unavailable')
        yield desktop
    finally:
        if desktop is not None:
            desktop.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.terminate()
            server.wait(timeout=10)


def main():
    artifact, output = Path(os.environ['MX6_ARTIFACT']),Path(os.environ['MX6_NATIVE_OUTPUT']) / 'source-observation.json'
    scenarios = json.loads((Path(__file__).parent / 'scenarios.json').read_text())['scenarios']
    chosen = ['baseline','report-january','report-december','acquisition-year-march',
              'last-asset-capacity','last-category-capacity','last-department-capacity']
    selected = [s for s in scenarios if s['id'] in chosen]
    report = {'candidate_sha256':digest(artifact),'phase':'running','scenarios':[],
              'scoring_performed':False,'lenient_evaluation_started':False}
    with tempfile.TemporaryDirectory(prefix='mx6-source-') as temporary:
        folder = Path(temporary)
        private = folder / 'candidate.xlsx'
        shutil.copy2(artifact,private)
        with office(folder) as desktop:
            for scenario in selected:
                material = openpyxl.load_workbook(os.environ['MX6_MATERIAL'])
                names = material.sheetnames
                document = desktop.loadComponentFromURL(private.as_uri(),'_blank',0,
                    (prop('Hidden',True),prop('ReadOnly',False),prop('MacroExecutionMode',0)))
                if document is None:
                    raise RuntimeError('Native workbook unavailable')
                row = {'id':scenario['id'],'checks':[],'source_input_checks':[],'model_controls':[]}
                try:
                    document.enableAutomaticCalculation(False)
                    for sheet,address,value in scenario['changes']:
                        value = datetime.fromisoformat(value['date']) if isinstance(value,dict) and 'date' in value else value
                        material[sheet][address] = value
                        cell = document.Sheets.getByName(sheet).getCellRangeByName(address)
                        if value is None: cell.clearContents(23)
                        elif isinstance(value,datetime): cell.setValue(to_excel(value,material.epoch))
                        elif isinstance(value,(int,float)): cell.setValue(value)
                        else: cell.setString(value)
                        actual = cell.getString() if isinstance(value,str) else cell.getValue()
                        target = to_excel(value,material.epoch) if isinstance(value,datetime) else value
                        if target is None:
                            if cell.getType().value != 'EMPTY': raise RuntimeError('Input clearing failed')
                        elif actual != target:
                            raise RuntimeError('Input mutation failed')
                    document.calculateAll()
                    def number(sheet,address,target,owner):
                        cell = document.Sheets.getByName(sheet).getCellRangeByName(address)
                        row['checks'].append({'sheet':sheet,'cell':address,'actual':cell.getValue(),
                            'expected':target,'error':cell.getError(),'owner':owner})
                    assets = [expected_asset(material,names,r) | {'category':material.worksheets[2].cell(r,4).value}
                              for r in range(5,205) if material.worksheets[2].cell(r,2).value]
                    dashboard = names[5]
                    for address,key in [('B7','cost'),('B8','ytd'),('B9','cumulative'),('B10','net'),('B15','annual')]:
                        number(dashboard,address,sum(a[key] for a in assets),'dashboard-summary')
                    number(dashboard,'B6',len(assets),'dashboard-summary')
                    number(dashboard,'B14',sum(a['net'] for a in assets) / sum(a['cost'] for a in assets),'dashboard-summary')
                    for rr in range(19,25):
                        category = material.worksheets[1].cell(rr-7,3).value
                        matching = [a for a in assets if a['category']==category]
                        number(dashboard,'B'+str(rr),len(matching),'dashboard-category')
                        for column,key in [('C','cost'),('D','ytd'),('E','cumulative'),('F','net')]:
                            number(dashboard,column+str(rr),sum(a[key] for a in matching),'dashboard-category')
                    for rr in range(5,16):
                        sheet = document.Sheets.getByName(names[8])
                        count = sheet.getCellRangeByName('B'+str(rr))
                        status = sheet.getCellRangeByName('C'+str(rr))
                        row['model_controls'].append({'row':rr,'label':sheet.getCellRangeByName('A'+str(rr)).getString(),
                            'value':count.getValue(),'error':count.getError(),'status':status.getString()})
                    if scenario['id']=='baseline':
                        regions = {names[1]:['B5:B7','C12:E31','B35:C64','B68:B71'], names[2]:['B5:M204'],
                                   names[6]:['A5:D404'],names[7]:['B2','A5:A204','C5:N204']}
                        regions[names[3]] = [openpyxl.utils.get_column_letter(29+2*m)+'5:'+openpyxl.utils.get_column_letter(29+2*m)+'204' for m in range(1,13)]
                        for sheet,ranges in regions.items():
                            for region in ranges:
                                source_cells = material[sheet][region]
                                if not isinstance(source_cells,tuple): source_cells=((source_cells,),)
                                for cells in source_cells:
                                    for cell in cells:
                                        if cell.value is None or cell.data_type=='f':continue
                                        native = document.Sheets.getByName(sheet).getCellRangeByName(cell.coordinate)
                                        target = to_excel(cell.value,material.epoch) if isinstance(cell.value,datetime) else cell.value
                                        actual = native.getString() if isinstance(target,str) else native.getValue()
                                        row['source_input_checks'].append({'sheet':sheet,'cell':cell.coordinate,
                                            'actual':actual,'expected':target,'error':native.getError(),'passed':actual==target and not native.getError()})
                    report['scenarios'].append(row)
                    output.write_text(json.dumps(report,indent=2)+'\n')
                finally:
                    document.setModified(False)
                    document.close(True)
                    material.close()
    report['phase']='observed'
    report['source_unchanged']=digest(artifact)==report['candidate_sha256']
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'phase':report['phase'],'scenarios':len(report['scenarios'])}),flush=True)


if __name__=='__main__':
    main()
