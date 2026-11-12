from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import openpyxl
from openpyxl.workbook.properties import CalcProperties

_candidates = [
    Path('/workspace/materials/workspace.xlsx'),
    Path('/workspace/materials/inputs.xlsx'),
    Path(__file__).resolve().parent.parent / 'tests/inputs.xlsx',
]
public = next((path for path in _candidates if path.is_file()), _candidates[0])
out=Path('/workspace/output/standard_time.xlsx')
w=openpyxl.load_workbook(public)
formulas=json.loads(Path(__file__).with_name('original_formulas.json').read_text())
for anchor,formula in formulas.items():
    sheet,cell=anchor.split('!');w[sheet][cell]=formula
w.properties.creator='';w.properties.lastModifiedBy=''
w.properties.lastPrinted=None
w.calculation=CalcProperties(calcId=191029,fullCalcOnLoad=True)
with tempfile.TemporaryDirectory(prefix='native-time-oracle-') as tmp:
    tmp=Path(tmp);inp=tmp/'input';converted=tmp/'converted';inp.mkdir();converted.mkdir()
    w.save(inp/out.name)
    subprocess.run(['libreoffice',f'-env:UserInstallation=file://{tmp}/profile','--headless','--convert-to','xlsx','--outdir',str(converted),str(inp/out.name)],check=True,timeout=600,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(converted/out.name,out)
