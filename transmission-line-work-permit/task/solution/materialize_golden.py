"""Materialize the supplied, hash-verified reference for cached oracle replay."""
import hashlib
import json
from pathlib import Path
import shutil
import sys


def main(workspace):
    task = Path(__file__).resolve().parents[1]
    manifest = json.loads((task / 'tests/golden_manifest.json').read_text())
    source = task.parent / 'golden' / manifest['filename']
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('Supplied Golden integrity failure')
    output = workspace / 'output'
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output / '\u5de5\u4f5c\u7968.docx')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
