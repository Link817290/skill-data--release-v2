"""Materialize the frozen reference deliverables for evaluator-side Oracle use."""
from pathlib import Path
import argparse
import shutil


package = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--out", type=Path, default=Path("/workspace/output"))
args = parser.parse_args()

if args.out.exists():
    raise SystemExit("Choose a new output directory.")
shutil.copytree(package / "golden", args.out)
