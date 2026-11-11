# Cooling Tower Selection Reconstruction

Complete the supplied counterflow cooling-tower workbook as described in
`task/instruction.md`. The workbook must remain live under input changes and
must select the smallest thermally feasible candidate before calculating the
selected air path, resistance and fan duty.

Build the isolated images from this package root:

```sh
docker build --target with-skill -t cooling-tower-selection-reconstruction-with-skill:1.0 -f task/environment/Dockerfile task/environment
docker build --target no-skill -t cooling-tower-selection-reconstruction-no-skill:1.0 -f task/environment/Dockerfile task/environment
docker build -t cooling-tower-selection-reconstruction-verifier:1.0 -f task/environment/Dockerfile.verifier .
```

The actor images contain only the issued workbook and runtime dependencies.
Only the with-skill target contains `/skills`; neither actor contains tests,
Golden files or solution code. The offline verifier privately owns `/tests` and
an independent copy of the issued source workbook.

The artifact scorer recalculates each submission in LibreOffice under the
baseline and nine input perturbations. Its formula-workbook Oracle and
independent Python engineering Oracle must agree. Run the verifier with the
candidate mounted at `/workspace/output/cooling_tower.xlsx`:

```sh
bash /tests/test.sh
```

Strict is continuous engineering completion with multiplicative damage events;
lenient is the independent conjunction of ten operational must-haves. Missing
infrastructure produces no score rather than a candidate zero.

A required source-bound semantic judge separately reviews only open engineering
claim scope, source fidelity and evidence meaning; it does not rejudge numerical
physics, formulas, selection or structure. Private tests ship one exact
Golden-only replay binding request/artifact/evidence hashes and sealing the raw
provider response, validated review, validation and manifest. New artifacts miss
that replay and require evaluator replay/fresh or are UNMEASURED. Actors cannot
see tests or the replay.

The task declares a mixed judge. `LLM_JUDGE_CACHE_DIR` selects an external
request-bound cache, `LLM_JUDGE_MODE` is `fresh` or `replay`, and
`LLM_JUDGE_TIMEOUT_SECONDS` sets the Responses timeout (default 600).
