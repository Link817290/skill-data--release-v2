"""Portable mixed-judge entry for shutdown-maintenance."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
TASK = HERE.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("answer", nargs="?", type=Path)
    parser.add_argument("--submission-dir", type=Path)
    parser.add_argument("--input", type=Path, default=TASK / "environment/workspace/input")
    parser.add_argument("--out", "--output", dest="out", type=Path)
    parser.add_argument("--publish-dir", type=Path)
    parser.add_argument("--reference-role", choices=["candidate", "author"], default="candidate")
    parser.add_argument("--mode", choices=["fresh", "replay"], default=os.environ.get("LLM_JUDGE_MODE", "fresh"))
    args = parser.parse_args()
    submission = args.submission_dir or args.answer or Path("/workspace/output")
    temporary = None
    if args.out is None:
        configured = os.environ.get("VERIFIER_OUTPUT_DIR") or os.environ.get("VERIFIER_LOG_DIR")
        if configured:
            publish = Path(configured)
        else:
            temporary = tempfile.TemporaryDirectory(prefix="shutdown-verifier-")
            publish = Path(temporary.name)
        evaluation = publish / "shutdown-maintenance-evaluation"
    else:
        evaluation = args.out
        publish = args.publish_dir or args.out.parent
    command = [
        sys.executable,
        "-B",
        str(HERE / "evaluate.py"),
        "--submission-dir",
        str(submission),
        "--input",
        str(args.input),
        "--out",
        str(evaluation),
    ]
    child_env = {
        **os.environ,
        "LLM_JUDGE_MODE": args.mode,
        "LLM_JUDGE_CACHE_DIR": os.environ.get(
            "LLM_JUDGE_CACHE_DIR", str(HERE / "mix_judge/cache")
        ),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    completed = subprocess.run(command, capture_output=True, text=True, env=child_env, check=False)
    result_path = evaluation / "result.json"
    if not result_path.is_file():
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        return 2
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("measurement_complete") is not True:
        if result.get("measurement_error"):
            print(result["measurement_error"], file=sys.stderr)
        return 2
    subprocess.run(
        [sys.executable, "-B", str(HERE / "write_reward.py"), str(result_path), str(publish)],
        check=True,
    )
    reward = json.loads((publish / "reward.json").read_text(encoding="utf-8"))
    print(json.dumps(reward, ensure_ascii=False))
    if temporary is not None:
        temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
