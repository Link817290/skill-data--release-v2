# Offline Measurement-Control Review

This task produces a rerunnable Python utility, its English usage guide and a
source-derived JSON/CSV review of mass and optical instrument-control records.
Issued inputs and scientific skills are under `task/environment/`; the exact
submission paths are listed in `task/instruction.md`.

## Build

Use the authorized `harbor-claude-code-aggregated:1.3` base, with Python 3.11,
NumPy 2.2.6, SciPy 1.13.1 and python-docx 1.2.0. Builds verify the original input
hashes. The private verifier installs the hash-pinned pyseccomp wheel offline.

```sh
docker build --target with-skill -t calibration-impact-review-with-skill:20261104 task/environment
docker build --target no-skill -t calibration-impact-review-no-skill:20261104 task/environment
docker build -f task/environment/Dockerfile.verifier -t calibration-impact-review-verifier:20261104 .
```

Both configurations use an offline actor and a separate public-network root
verifier. Only the with-skill actor contains `/skills`. Actor images contain no
tests, Golden, Oracle code or judge credentials. The verifier protects its grader,
reference and original workspace, and runs candidate code in disposable copies as
UID 65534 with judge variables removed and IP sockets denied.

## Oracle And Scoring

Build the declared images, set judge credentials externally, then run the actual
Harbor Oracle:

```sh
harbor run --path task --agent oracle --jobs-dir /tmp/calibration-harbor
```

For no-skill, materialize an isolated task copy outside the package and replace
its `task.toml` with `task_no_skill.toml`. The Oracle uses the maintained reference
implementation bundled privately under `solution/`, executes it against the issued
CSVs and generates the JSON/CSV outputs. It does not copy precomputed result files.

The Harbor grading entrypoint inside the private verifier is
`/tests/test.sh [submission_directory]`; `/task/tests` is a compatibility link.
Its default submission is
`/workspace/output`; `VERIFIER_OUT` selects the external log directory. Supply
`LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY` externally. The optional model variable
is `LLM_JUDGE_MODEL`, defaulting to `gpt-5.6-sol`.

Fresh submissions use the OpenAI Responses API at `/v1/responses`.
`LLM_JUDGE_CACHE_DIR` selects an external cache bound to the complete
source/candidate request, model and semantic contract; `LLM_JUDGE_MODE` is
`fresh` or `replay`, and `LLM_JUDGE_TIMEOUT_SECONDS` defaults to 600.
Exact cache replay works without an endpoint or key. Keep logs, caches and job
directories outside the package. Infrastructure failures produce `UNMEASURED`
and no reward. See `RUBRIC.md` for numerical owners, semantic evidence and the
independent completion requirements.

`golden/golden_replay/` is the sole packaged replay exception: it contains exactly the
current Golden request, artifact/evidence hash manifest, raw response, evidence, and validated
review. It excludes ordinary candidates, provider history, and credentials. The directory
is outside `task/` and is not actor-visible. The production judge accepts it only in
explicit-replay mode against current Golden hashes; any artifact or contract change is a hard miss
that requires fresh review.
