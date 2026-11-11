from pathlib import Path
import argparse
import json
import shutil
import subprocess
import tempfile
import openpyxl


def build(source,destination):
 workbook=openpyxl.load_workbook(source)
 formulas=json.loads((Path(__file__).parent/'formulas.json').read_text())
 for cell,formula in formulas.items():workbook['Sheet1'][cell]=formula
 destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
 workbook.save(destination)
 with tempfile.TemporaryDirectory(prefix='tower-original-oracle-')as tmp:
  tmp=Path(tmp)
  result=subprocess.run(['libreoffice',f'-env:UserInstallation=file://{tmp}/profile','--headless','--convert-to','xlsx','--outdir',str(tmp),str(destination)],capture_output=True,text=True)
  if result.returncode or not (tmp/destination.name).exists():raise RuntimeError(result.stdout+result.stderr)
  shutil.copy2(tmp/destination.name,destination)


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--source',default='/workspace/materials/workspace.xlsx');parser.add_argument('--output',default='/workspace/output/cooling_tower.xlsx');args=parser.parse_args()
 build(args.source,args.output)
