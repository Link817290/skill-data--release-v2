from pathlib import Path
import argparse
import shutil


parser = argparse.ArgumentParser(description="Materialize the packaged reference deliverable.")
parser.add_argument("--out", type=Path, default=Path("/workspace/output"))
args = parser.parse_args()

task = Path(__file__).resolve().parents[1]
golden = task / "golden"
if not golden.is_dir():
    golden = task.parent / "golden"
if not golden.is_dir():
    golden = Path("/golden")
if not golden.is_dir():
    raise SystemExit("Packaged Golden directory is unavailable")

args.out.mkdir(parents=True, exist_ok=True)
if any(args.out.iterdir()):
    raise SystemExit("Choose an empty output directory")
for source in golden.iterdir():
    if source.is_file():
        shutil.copy2(source, args.out / source.name)
