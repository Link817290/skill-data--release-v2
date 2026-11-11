"""Portable entry point for trusted native workbook observations."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--artifact',required=True)
    parser.add_argument('--material',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--family',choices=['valid','diagnostics','source','all'],default='all')
    args=parser.parse_args()
    artifact,material,output=Path(args.artifact).resolve(),Path(args.material).resolve(),Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    if args.family=='valid':
        from financial_native import observe
        scenarios=json.loads((HERE/'scenarios.json').read_text())['scenarios']
        records=[]
        for scenario in scenarios:
            folder=output/scenario['id'];folder.mkdir()
            result=observe(candidate=artifact,material=material,output=folder/'observation.json',scenario=scenario)
            if result['phase']!='observed':raise RuntimeError('Native business measurements incomplete')
            records.append({'id':scenario['id'],'phase':result['phase']})
        (output/'status.json').write_text(json.dumps({'records':records,'expected':44},indent=2)+'\n')
        return
    if args.family in ('diagnostics','source'):
        os.environ.update(MX6_ARTIFACT=str(artifact),MX6_MATERIAL=str(material),MX6_NATIVE_OUTPUT=str(output))
        if args.family=='diagnostics':
            from diagnostic_native import main as native_main
        else:
            from source_native import main as native_main
        native_main()
        return
    def run(family):
        target=output/family
        command=[sys.executable,'-B',str(__file__),'--artifact',str(artifact),'--material',str(material),
                 '--output',str(target),'--family',family]
        start=datetime.now(timezone.utc).isoformat()
        done=subprocess.run(command,capture_output=True,text=True)
        target.mkdir(parents=True,exist_ok=True)
        (target/'execution.json').write_text(json.dumps({'command':command,'started_at':start,
            'finished_at':datetime.now(timezone.utc).isoformat(),'exit_code':done.returncode,
            'stdout':done.stdout,'stderr':done.stderr},indent=2)+'\n')
        if done.returncode:raise RuntimeError('Native '+family+' extraction failed; no score assigned')
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(run,['valid','diagnostics','source']))


if __name__=='__main__':main()
