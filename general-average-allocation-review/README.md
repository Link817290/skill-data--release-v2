# General-average allocation review

Review the supplied adjustment and three judgments and deliver an English technical
memorandum at `/workspace/deliverables/general_average_review.md` and an English
reconciliation schedule at
`/workspace/deliverables/general_average_schedule.csv`.

## Package and images

The package root contains only `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/` and `task/`. Build from this package root:

```sh
docker build --pull=false --target with-skill -t general-average-allocation-review-skills:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false --target no-skill -t general-average-allocation-review:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false -t general-average-allocation-review-verifier:1.3 -f task/environment/Dockerfile.verifier .
```

All images derive from `harbor-claude-code-aggregated:1.3`. Both actor conditions
contain the same four source PDFs and run without network access. Only the
with-skill target copies the task skill to `/skills`. Golden, evaluator code,
Oracle code and judge credentials are not actor-visible.

The Oracle entrypoint is `task/solution/solve.sh`; it writes both required files
under `/workspace/deliverables`. With a candidate mounted at that directory, run
the verifier entrypoint as `bash /tests/test.sh`.

Configure the verifier with exactly six public variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default
`gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` (`fresh`, `replay`, or
`auto`) and `LLM_JUDGE_TIMEOUT_SECONDS`. Credentials and ordinary response caches
remain outside the package. Fresh mode evaluates new submissions. The package
contains only the request-, artifact- and runtime-bound Golden replay. Replay
misses and judge or runtime failures exit nonzero without publishing a score.

## Scoring boundary

The mixed evaluator checks files, source hashes, monetary controls, roll-forward
arithmetic and source locators deterministically. It uses the evidence-bound LLM
judge for professional maritime and legal meaning, including adoption, attribution,
negation and equivalent language. A positive semantic decision must quote exact
candidate evidence and, for a scored finding, a supplied-record pinpoint. Numeric
findings additionally retain deterministic amount checks.

`reward` is the continuous strict score. The separately reported lenient score is
the documented binary usability lens in `RUBRIC.md`. Golden scores strict and
lenient `1.0`; an invalid or missing candidate is a measured candidate failure.
