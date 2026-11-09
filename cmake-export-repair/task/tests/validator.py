#!/usr/bin/env python3
"""Score one submitted workspace under both lenses and print the detail.

    python3 validator.py /workspace                # print the detail JSON
    python3 validator.py /workspace --out /logs/verifier

Both lenses come out of one call, so the emitted reward files always agree:

    reward_strict   continuous professional capability score
    reward_lenient  independent binary delivery-completeness score
    reward          alias of reward_strict

The scoring rules are stated in RUBRIC.md and implemented in test_outputs.py.
Mechanical checks are deterministic; reasoning uses an evidence-bound LLM judge.
Configure LLM_JUDGE_BASE_URL, LLM_JUDGE_MODEL, LLM_JUDGE_API_KEY; cache
entries are bound to source, rubric, model and candidate hashes. Missing service
configuration or invalid judge evidence is an infrastructure error, never success.
When that happens, all public rewards are UNMEASURED/null; delivery checks may be
retained only as non-reward diagnostics.
"""
import argparse
import json
from pathlib import Path

from test_outputs import score_workspace, unmeasured_detail, write_scores, write_unmeasured


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workspace", nargs="?", default="/workspace")
    ap.add_argument("--out", type=Path, help="also write the reward files here")
    args = ap.parse_args()

    try:
        detail = score_workspace(args.workspace)
    except Exception as exc:
        detail = unmeasured_detail(args.workspace, exc)
        print(json.dumps(detail, indent=2, sort_keys=True))
        if args.out:
            write_unmeasured(detail, args.out)
        return 2
    print(json.dumps(detail, indent=2, sort_keys=True))
    if args.out:
        write_scores(detail, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
