"""One image-local public verifier: actual observations, then one settlement."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from public_recipe import prepare
from settle import aggregate

HERE=Path(__file__).resolve().parent


def read(path):return json.loads(Path(path).read_text())
def save(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def inventory(root):
    result={}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() and not path.resolve().is_relative_to(root):raise ValueError('Artifact source link leaves the declared read-only artifact')
        if not path.is_file() or any(part in ['.godot','.git','__pycache__'] for part in path.relative_to(root).parts):continue
        if not path.resolve().is_relative_to(root):raise ValueError('Artifact source link leaves the declared read-only artifact')
        result[str(path.relative_to(root))]=sha(path)
    return result


def drop():
    if os.geteuid()==0:
        os.setgroups([]);os.setgid(20005);os.setuid(20005)


def own(path):
    if os.geteuid()==0:os.chown(path,20005,20005)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artifact',type=Path,required=True);parser.add_argument('--layout',choices=['auto','workspace','delivery'],default='auto');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--mode',choices=['fresh','replay'],default='replay');parser.add_argument('--bundle',type=Path);parser.add_argument('--evidence',type=Path);parser.add_argument('--cache-dir',type=Path);args=parser.parse_args()
    artifact=args.artifact.resolve()
    if args.layout=='workspace' or (args.layout=='auto' and (artifact.name=='workspace' or (artifact/'output').is_dir())):artifact=artifact/'output'
    out=args.output.resolve();assert not out.is_relative_to(artifact);out.mkdir(parents=True,exist_ok=True);os.chmod(out,0o700)
    assert os.geteuid() in (0,20005),'Verifier must run as root or the declared image user UID20005.'
    cache=(args.cache_dir or (out/'semantic-cache' if args.mode=='fresh' else HERE/'cache')).resolve()
    if args.mode=='fresh':cache.mkdir(parents=True,exist_ok=True);os.chmod(cache,0o700)
    before=inventory(artifact);bundle_path=args.bundle
    try:
        program_dir=out/'program';program_dir.mkdir()
        argv=[sys.executable,str(HERE/'program.py'),'--artifact',str(artifact),'--output',str(program_dir)];run=subprocess.run(argv,capture_output=True,text=True,timeout=600);save(program_dir/'execution.json',dict(argv=argv,exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr))
        program=read(program_dir/'program_result.json');assert program['status']=='measured',program.get('error')
        if program.get('missing_required_project'):
            result=dict(status='measured',rewards=dict(strict=0.0,lenient=0),reason='Complete input inventory proves no required runnable project.',source_measurements=dict(program='program/program_result.json'),artifact_files=before)
        else:
            argv=[sys.executable,str(HERE/'semantic.py'),'--artifact',str(artifact),'--output',str(out/'semantic'),'--cache-dir',str(cache),'--mode',args.mode]
            if bundle_path:argv+=['--bundle',str(bundle_path)]
            if args.evidence:argv+=['--evidence',str(args.evidence)]
            run=subprocess.run(argv,capture_output=True,text=True,timeout=2600);save(out/'semantic-execution.json',dict(argv=argv,exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr));semantic=read(out/'semantic/semantic_result.json');assert semantic['status']=='measured',semantic.get('error')
            evidence=semantic['source_bundle']['receiver_evidence'];recipe=prepare(artifact,evidence);save(out/'public-recipe.json',recipe)
            if recipe['status']=='known_missing':runtime=dict(status='measured',success=False,reason='Complete public register contains no required concrete export recipe; no unknown tool is labeled false.')
            else:
                assert recipe['status']=='measured',recipe.get('why')
                work=Path(tempfile.mkdtemp(prefix='godot-public-recipe-'));own(work);capture=work/'capture';capture.mkdir();own(capture)
                env={key:value for key,value in os.environ.items() if key in ['PATH','LANG','LC_ALL','FX_TOOLS']}
                argv=[sys.executable,str(HERE/'runtime_capture.py'),'--artifact',str(artifact),'--recipe',str(out/'public-recipe.json'),'--output',str(capture),'--work-root',str(work/'runtime')]
                # The recipe is public input. The root-private semantic logs,
                # cache and provider environment remain inaccessible to Godot.
                public_recipe=work/'recipe.json';save(public_recipe,recipe);own(public_recipe);argv[argv.index('--recipe')+1]=str(public_recipe)
                run=subprocess.run(argv,capture_output=True,text=True,env=env,preexec_fn=drop if os.geteuid()==0 else None,timeout=220);save(out/'runtime-execution.json',dict(argv=argv,exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr,uid=20005,provider_environment_excluded=True));runtime=read(capture/'receipt.json')
                import shutil
                shutil.copytree(capture,out/'runtime');shutil.rmtree(work)
            save(out/'runtime_result.json',runtime);result=aggregate(program,semantic,runtime)
            result['source_measurements']=dict(program=dict(path='program/program_result.json',sha256=sha(program_dir/'program_result.json')),semantic=dict(path='semantic/semantic_result.json',sha256=sha(out/'semantic/semantic_result.json')),runtime=dict(path='runtime_result.json',sha256=sha(out/'runtime_result.json')))
            result['artifact_files']=before;result['parameters_sha256']=sha(HERE/'params.json');result['owner_policy_sha256']=sha(HERE/'owner_policy.json')
        assert inventory(artifact)==before,'Artifact changed during verification'
        result.update(artifact_unchanged=True,new_actor_runs=0);save(out/'reward.json',result);(out/'reward.txt').write_text(str(result['rewards']['strict'])+'\n');(out/'reward_strict.txt').write_text(str(result['rewards']['strict'])+'\n');print(json.dumps(dict(status=result['status'],rewards=result['rewards'])))
    except Exception as error:
        save(out/'reward.json',dict(status='needs_review',error=str(error),rewards=dict(strict=None,lenient=None),new_actor_runs=0));print(str(error));raise SystemExit(2)


if __name__=='__main__':main()
