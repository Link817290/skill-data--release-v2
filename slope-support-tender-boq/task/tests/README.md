# Evaluation Runtime

`entrypoint.py` is the production scorer. It runs the offline program validator,
then the source-bound semantic judge, and writes the standard strict and lenient
reward files. `validator.py` owns workbook structure, section selection, item
matching, units, quantities, formulas, traceability, controls, and the continuous
repeat-integrity adjustment.

The semantic runtime accepts `auto`, `fresh`, and `replay` through
`LLM_JUDGE_MODE`. Configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`,
`LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, and
`LLM_JUDGE_TIMEOUT_SECONDS` externally. The package contains only the exact
Golden replay fixture. Missing or invalid semantic measurement produces
`UNMEASURED`; it is never converted to a candidate zero.

`ground_truth.json` and `reference/quantity_provenance.json` are evaluator-only
records. Unit and integration tests exercise accepted table layouts, equivalent
headers, quantity dependencies, control closure, pricing formulas, and the public
reward-file contract.
