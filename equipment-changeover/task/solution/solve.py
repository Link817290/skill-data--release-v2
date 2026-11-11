from pathlib import Path
import argparse,shutil
p=argparse.ArgumentParser(description='Materialize the frozen private reference deliverables. This is not a candidate-visible solver.')
p.add_argument('--out',type=Path,required=True);a=p.parse_args();task=Path(__file__).resolve().parents[1];package=task.parent
if a.out.exists():raise SystemExit('Choose a new output directory.')
shutil.copytree(package/'golden',a.out)
