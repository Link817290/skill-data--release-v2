# Runtime evaluation

The public instruction declares the workbook, report and calculation-file paths.
Run from the task directory:

```sh
python tests/evaluate.py --submission-dir /workspace/output --out /external/evaluation
```

Configure `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY` in the private verifier
environment. See `mix_judge/settings.json` for review settings. The complete score
requires both numerical checks and a valid text review. No appearance score applies.

`test.sh` defaults to `/workspace/output` and writes under `/logs/verifier`.
Required files that are missing, unreadable or ambiguous fail the public contract.
Calculation-file presence alone does not establish execution reproducibility.

`workbook_verify.py` reconstructs the source records and verifies the submitted
allocations and objective values. Public sheet/header names and units apply;
row/column order and equivalent optimal allocations may differ. Optional sheets
are not gates. Formula cells need saved evaluated values. `verify.py` supplies
the canonical intermediate-data checks and independent improvement search used
by the workbook verifier; its internal score is not the final mixed score.

The text review reads the report, workbook evidence, reference facts and Golden.
These files remain private. `--semantic-replay /external/response.json` requires
an adjacent receipt manifest and an exact request hash match. A replay is not a
fresh service call. Use a new output directory for each evaluation. Incomplete
required measurements withhold the combined result.
