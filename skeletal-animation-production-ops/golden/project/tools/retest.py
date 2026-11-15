"""Repeat client-effect checks and bind observations to this exact project."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import shutil
import subprocess


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    project=Path(__file__).resolve().parents[1];output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    engine=shutil.which('godot') or shutil.which('godot4')
    if not engine:raise SystemExit('Godot4.4.1 executable is required')
    manifest=json.loads((project/'tools/original_pngs.json').read_text())
    actual={str(path.relative_to(project/'assets/frames')):sha(path) for path in (project/'assets/frames').rglob('*.png')}
    if actual!=manifest:raise SystemExit('Original PNG names or contents do not match the delivered reference manifest')
    records=[]
    for script,destination,verification in [('verify_effects.gd',output/'api',True),('verify_world_heading.gd',output/'world-heading.json',True),('verify_demo.gd',output/'demo.json',False)]:
        command=[engine,'--headless','--fixed-fps','60','--path',str(project),'--script',str(project/'tools'/script),'--',str(destination)]+(['--verification'] if verification else [])
        process=subprocess.run(command,capture_output=True,text=True)
        records.append(dict(command=command,exit_code=process.returncode,stdout=process.stdout,stderr=process.stderr))
    result=dict(tested_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),engine_version=subprocess.run([engine,'--version'],capture_output=True,text=True,check=True).stdout.strip(),project_files={str(path.relative_to(project)):sha(path) for path in project.rglob('*') if path.is_file() and '.godot' not in path.relative_to(project).parts},source_png_count=len(actual),delivery_fps=30,original_sequence_fps='unknown',producer='Public-API observations from actual Godot nodes and externally recorded process ticks/signals; no candidate success counter.',results=records,passed=all(row['exit_code']==0 for row in records))
    (output/'tested-build.json').write_text(json.dumps(result,indent=2)+'\n')
    print('CLIENT RETEST:', 'PASS' if result['passed'] else 'FAIL')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
