# Employee Equity Dilution Ledger

Build an English, formula-driven equity award roll-forward and dilution ledger
from the supplied annual report and proxy statement. The required workbook is
`/workspace/employee_equity_dilution_ledger.xlsx`; see `task/instruction.md` and
`RUBRIC.md` for the source and scoring contracts.

Build the actor image from the package root:

```sh
docker build --pull=false -t employee-equity-dilution-ledger:1.0 task/environment
```

The image includes `pdftotext`, openpyxl and lxml, and issues only the two filing
materials. Actor networking is disabled by the task configuration. For the
no-skill arm, use an external copy of `task/` with `task_no_skill.toml` selected
as `task.toml` and do not attach the packaged dilution Skills. Both arms use the
same instruction and deterministic scorer.

The source-derived Oracle is `task/solution/solve.sh`. With `WORKSPACE_ROOT`
pointing at a workspace containing `materials/annual_report.pdf` and
`materials/proxy_statement.html`, it parses the filings and writes the requested
workbook. It does not read Golden or verifier ground truth.

Score a workbook with:

```sh
python3 task/tests/validator.py /workspace/employee_equity_dilution_ledger.xlsx
```

The program judge evaluates nine weighted positive owners and enumerated,
deduplicated damage instances. `reward` equals continuous strict; lenient is an
independent must-do ledger lens. Open-ended interpretation, source limitation and
adopted-inversion checks require the source-bound semantic gate. Gate failure is
UNMEASURED and removes numeric rewards. The package may contain only an exact
Golden response under `task/tests/mix_judge/golden_replay/`; new artifact misses
require fresh evaluator access. Actors cannot see verifier tests, replies or credentials.
Fresh access uses only OpenAI Responses with a GPT judge through
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY` and optional `LLM_JUDGE_MODEL`.
`LLM_JUDGE_TIMEOUT_SECONDS` controls the request timeout and
`LLM_JUDGE_CACHE_DIR` holds evaluator-only request-bound replies.
`LLM_JUDGE_MODE` selects fresh or exact replay behavior.
Protocol, completion, JSON or schema failures are UNMEASURED.
`task/tests/test.sh` writes numeric rewards and detailed evidence to
`VERIFIER_OUTPUT_DIR` (default `/logs/verifier`) and preserves the submitted
workbook for audit. Runtime logs, snapshots, caches and metrics are process state,
not release-package inputs.
