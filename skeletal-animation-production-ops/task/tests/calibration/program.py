"""Independent original program observations, run without provider credentials."""
from pathlib import Path
import argparse
import csv
import json
import os
import shutil
import site
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
TESTS=HERE.parent


def drop():
    if os.geteuid()==0:
        os.setgroups([]);os.setgid(20005);os.setuid(20005)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artifact',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    artifact=args.artifact.resolve()
    if not all((artifact/'project'/name).is_file() for name in ['project.godot','stage.gd','stage.tscn']):
        result=dict(status='measured',completion={f'C{i:02}':0 for i in range(1,16)},ordinary_heading=False,default_stage_usable=False,missing_required_project=True);(args.output/'program_result.json').write_text(json.dumps(result,indent=2)+'\n');return
    assert os.geteuid() in (0,20005),'Verifier must run as root or the declared image user UID20005.'
    work=Path(tempfile.mkdtemp(prefix='godot-program-'))
    if os.geteuid()==0:os.chown(work,20005,20005)
    copied=work/'artifact';shutil.copytree(artifact,copied,ignore=shutil.ignore_patterns('.godot','.git','__pycache__'))
    for path in [copied,*copied.rglob('*')]:
        if os.geteuid()==0:os.chown(path,20005,20005)
        if path.is_dir():path.chmod(0o755)
        else:path.chmod(path.stat().st_mode|0o644)
    observed=work/'observations';observed.mkdir()
    if os.geteuid()==0:os.chown(observed,20005,20005)
    env={key:value for key,value in os.environ.items() if key in ['PATH','LANG','LC_ALL','FX_TOOLS','DISPLAY','TASK_WORKSPACE']};env.update(HOME=str(work),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',TMPDIR=str(work))
    original=Path(env.get('TASK_WORKSPACE','/workspace'))/'project';env['FX_ORIGINAL_PROJECT']=str(original)
    env['PYTHONPATH']=os.pathsep.join([site.getusersitepackages(),*site.getsitepackages()])
    argv=[sys.executable,str(TESTS/'validator.py'),'--submission',str(copied),'--report',str(observed)]
    run=subprocess.run(argv,capture_output=True,text=True,env=env,preexec_fn=drop if os.geteuid()==0 else None,timeout=360)
    world=[os.environ.get('GODOT','godot'),'--headless','--fixed-fps','60','--path',str(copied/'project'),'--script',str(HERE/'probe_world_heading.gd'),'--',str(observed/'world-heading.json'),'--verification']
    heading=subprocess.run(world,capture_output=True,text=True,env=env,preexec_fn=drop if os.geteuid()==0 else None,timeout=180)
    shutil.copytree(observed,args.output/'observations')
    records=[dict(argv=argv,exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr),dict(argv=world,exit_code=heading.returncode,stdout=heading.stdout,stderr=heading.stderr)]
    try:
        with (observed/'checks.csv').open(encoding='utf-8-sig',newline='') as stream:checks=list(csv.DictReader(stream))
        by_id={row['id']:row for row in checks};assert all(f'C{i:02}' in by_id for i in range(1,16)),'Incomplete technical observations'
        completion={key:float(row['earned'])/float(row['available']) for key,row in by_id.items() if key.startswith('C') and float(row['available'])>0}
        world_result=json.loads((observed/'world-heading.json').read_text());ordinary=all(row['heading_passed'] for row in world_result['cases'] if row['parent_rotation']==0);completion['C09']=min(completion['C09'],int(all(row['heading_passed'] for row in world_result['cases'])))
        default=json.loads((observed/'default-entry-observations.json').read_text())
        result=dict(status='measured',completion=completion,ordinary_heading=ordinary,default_stage_usable=default['usable_default_stage'],execution_records=records,observer_runtime_home_is_private_not_public_recipe=True)
    except Exception as error:result=dict(status='needs_review',error=str(error),execution_records=records,reward=None)
    (args.output/'program_result.json').write_text(json.dumps(result,indent=2)+'\n');shutil.rmtree(work)
    if result['status']!='measured':raise SystemExit(2)


if __name__=='__main__':main()
