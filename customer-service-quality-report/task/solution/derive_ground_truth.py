import argparse
import json
from pathlib import Path
from solve import load_facts

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    task = Path(__file__).resolve().parents[1]
    facts = load_facts(task/"environment/workspace/materials")
    current = json.loads((task/"tests/ground_truth.json").read_text(encoding="utf-8"))
    if args.check:
        assert facts == current["facts"], "Source-derived facts drifted"
        print("Source regeneration matches frozen answer facts")
    else:
        current["facts"] = facts
        (task/"tests/ground_truth.json").write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding="utf-8")
