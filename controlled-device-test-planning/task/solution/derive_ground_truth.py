"""Regenerate Golden through solve.py; --check never changes Golden."""
from pathlib import Path
import argparse
import hashlib
import json
import tempfile

from solve import derive, workbook_bytes, ARTIFACT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    task=Path(__file__).resolve().parents[1]
    package=task.parent
    materials=task/'environment/workspace/materials'
    contract,facts,applicability,rows,sources=derive(materials)
    payload=workbook_bytes(contract,facts,applicability,rows)
    paths=[package/'golden'/ARTIFACT,task/'tests/golden'/ARTIFACT]
    if args.check:
        failures=[str(p.relative_to(package)) for p in paths if not p.exists() or p.read_bytes()!=payload]
        print(json.dumps({'status':'fail' if failures else 'pass','mismatches':failures,'sha256':hashlib.sha256(payload).hexdigest()}))
        return bool(failures)
    for path in paths:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(payload)
    print(json.dumps({'status':'written','case_count':len(rows),'sha256':hashlib.sha256(payload).hexdigest()}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
