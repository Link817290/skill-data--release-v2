# Manufacturing standard-time workbook reconstruction

## Task

The actor receives `task/environment/workspace/materials/workspace.xlsx` and
restores the missing measurement, standard-time, capacity, machine-demand, and
staffing formulas. The only deliverable is
`/workspace/output/standard_time.xlsx`. The workbook must preserve its original
worksheets, source values, layout, and Chinese business labels.

## Runtime

Both conditions build `task/environment/Dockerfile`, which is pinned to
`harbor-claude-code-aggregated:1.3` and checks LibreOffice plus
`openpyxl==3.1.5` during the build. `task/task.toml` mounts the packaged
manufacturing skill; `task/task_no_skill.toml` uses the same instruction,
workspace, output contract, timeouts, and evaluator without that skill.
Actor network access is disabled.

Build the cold environment from the package root:

```bash
docker build -t manufacturing-standard-time-reconstruction:1.0 task/environment
```

Run the Oracle in that image with `task/solution` mounted at `/solution`:

```bash
docker run --rm \
  -v "$PWD/task/solution:/solution:ro" \
  -v "$PWD/.oracle-output:/workspace/output" \
  manufacturing-standard-time-reconstruction:1.0 \
  sh /solution/solve.sh
```

Run the actual scorer with tests mounted read-only and a writable external log
directory:

```bash
docker run --rm \
  -v "$PWD/task/tests:/tests:ro" \
  -v "$PWD/golden:/workspace/output:ro" \
  -v "$PWD/.verifier-logs:/logs" \
  manufacturing-standard-time-reconstruction:1.0 \
  sh /tests/test.sh /workspace/output
```

The Golden workbook scores `strict=1.0` and `lenient=1.0`. The scorer is fully
programmatic and needs no API, credential, network, private host path, or
provider cache. Details of the seven positive owners, operation-isolation
tests, activity-basis retention, and the independent lenient usability contract
are defined in `RUBRIC.md` and implemented in `task/tests/validator.py`.
The verifier requires LibreOffice for native formula recalculation; if it is
unavailable the run is reported as infrastructure-unmeasured rather than a
candidate score of zero.

## Package contents

The package root contains only `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/`, and `task/`. Golden contains only the reference
workbook. Runtime inputs, skills, Oracle code, and evaluator fixtures remain in
their designated directories under `task/`.
