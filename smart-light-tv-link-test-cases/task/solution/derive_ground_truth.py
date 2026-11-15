import sys
sys.dont_write_bytecode = True
import argparse
import sys
import tempfile
from pathlib import Path

import openpyxl

from solve import write_workbook


def semantic_cells(path):
    book = openpyxl.load_workbook(path, data_only=False)
    return {sheet.title: list(sheet.values) for sheet in book.worksheets}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    materials = root / "environment/workspace/materials"
    golden = root / "golden/linkage-test-cases.xlsx"
    if args.check:
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder) / "candidate.xlsx"
            write_workbook(materials, candidate)
            equal = semantic_cells(candidate) == semantic_cells(golden)
            print("reference semantic drift: " + ("none" if equal else "DETECTED"))
            sys.exit(0 if equal else 1)
    else:
        write_workbook(materials, golden)
