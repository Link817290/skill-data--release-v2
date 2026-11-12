"""Platform adapter for the single canonical Program Judge contract."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def lenient_score(detail: dict) -> float:
    """Require the minimum coherent court filing and both lawful request channels."""
    fractions = {item["id"]: float(item["fraction"]) for item in detail["items"]}
    jurisdiction_chain_count = sum(
        fractions.get(item_id, 0.0)
        for item_id in ("G_J_RELATION", "G_J_ORIGIN", "G_J_RELIEF")
    )
    required = (
        jurisdiction_chain_count >= 2.0,
        fractions.get("G_J_FORUM_EXCLUSIVITY", 0.0) >= 1.0,
        fractions.get("G_F_CHANNEL", 0.0) >= 1.0,
        fractions.get("G_T_CHANNEL", 0.0) >= 1.0,
    )
    return float(all(required))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    contract = next((parent / 'rubric-contract.json' for parent in (here, *here.parents)
                     if (parent / 'rubric-contract.json').is_file()), None)
    if contract is None:
        parser.error('rubric-contract.json was not found beside tests or its ancestors')
    artifact = args.submission / "output" if (args.submission / "output").is_dir() else args.submission
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(here / 'program_judge/task_judge.py'), str(artifact), '--contract', str(contract)], capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stderr)
        return result.returncode
    detail = json.loads(result.stdout)
    lenient = lenient_score(detail)
    detail.update(reward=detail['final_score'], reward_strict=detail['final_score'], reward_lenient=lenient)
    print(json.dumps(detail, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
