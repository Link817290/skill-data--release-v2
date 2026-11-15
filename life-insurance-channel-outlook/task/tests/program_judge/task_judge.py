#!/usr/bin/env python3
"""Task adapter starter. Implement the three explicit observation layers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from program_judge_runtime import ProgramJudge, load_contract, sha256
from business_relations import extract_raw, evaluate


HERE = Path(__file__).resolve().parent
CANONICAL_CONTRACT = next((p / 'rubric-contract.json' for p in HERE.parents if (p / 'rubric-contract.json').is_file()), None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    facts = json.loads((HERE.parent / 'material-facts.json').read_text(encoding='utf-8'))['facts']
    result = evaluate(extract_raw(args.artifact.resolve()), judge, facts)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
