# Golden deliverable

The hidden reference solution writes `/workspace/regime_map.xlsx` inside the container. The
`golden/regime_map.xlsx` in this repository is a copy of that reference answer, produced by
the same solution, and is used to verify that the scorer is self-consistent.

Note that a Golden score of 1.000000 is not an agent result. It means only that the reference
answer and the scorer agree.

`solve.sh` reads frozen CSVs from `/workspace` and writes
`/workspace/regime_map.xlsx` in the rebuilt environment. For a local isolated run,
pass `--workspace /path/to/clean/workspace`; `--output` optionally overrides the
destination. The solution requires the evaluator's `workbook.py` helper under the
task's `tests` directory or `/tests`, but does not read the checked-in Golden.
