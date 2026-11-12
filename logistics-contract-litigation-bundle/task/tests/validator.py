#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "program_judge"))
from task_judge import score_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    artifact = args.artifact
    for candidate in (artifact / "artifacts" / "output", artifact / "output"):
        if candidate.is_dir():
            artifact = candidate
            break
    result = score_path(artifact)
    destination = args.output or args.json
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
