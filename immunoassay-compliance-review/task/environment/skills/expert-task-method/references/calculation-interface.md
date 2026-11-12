# Calculation Interface

## Scope and choice

`scripts/calculate.py` is relative to the directory containing `SKILL.md`, not
the workbook or working directory. Python 3 and its standard library suffice.
It reads explicit numeric requests and returns JSON; it does not discover files,
choose valid observations, infer acceptance rules, or write a report.

Which interface best fits the existing extraction work? `--input` accepts a JSON
file, stdin accepts the same JSON, and `calculate(request)` is importable into a
Python reader. Both CLI interfaces accept one object or a nonempty array of
objects; array results retain input order. Identity and evidence belong in the
caller's surrounding records, not in extra request fields.

## Minimal interface example

These numbers are invented solely to illustrate the API. With the skill
directory as the working directory, a stdin request looks like:

```bash
python3 scripts/calculate.py <<'JSON'
{"operation":"summary","values":[2,4,6]}
JSON
```

The result contains `operation` and `result`; here `result` includes `n=3`,
`df=2`, `mean=4`, `sample_sd=2`, and `cv_percent=50`. For a request file with the
same content, the equivalent interface is:

```bash
python3 scripts/calculate.py --input request.json
```

An existing Python reader can import the same implementation. In this example,
`skill_directory` is the resolved directory containing the loaded `SKILL.md`:

```python
import importlib.util
from pathlib import Path

script = Path(skill_directory) / "scripts" / "calculate.py"
spec = importlib.util.spec_from_file_location("review_calculator", script)
calculator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calculator)
result = calculator.calculate({"operation": "summary", "values": [2, 4, 6]})
```

## Operation selection

`--describe` returns the required fields, defaults, and purpose of every
operation. The available names are `summary`, `rounded_mean`, `log_threshold`,
`robust_threshold`, `sir`, `ratio`, `floating`, `suitability`, `interpolate`,
and `round`. Does the selected operation match the intended quantity, pairing,
population, and precision chain, rather than merely a similar label?

Compound operations retain binary64 precision without intermediate rounding.
If the source convention rounds intermediate statistics, is a composition of
primitive operations and explicit `round` calls needed instead? Python's built-in
`round` does not in general share the tool's decimal half-away-from-zero rule.
An interface success does not establish that these conventions match the source.

Could a discrepancy at a rounding boundary come from the review's own arithmetic?
`round` cannot recover a decimal midpoint lost before it receives the value.
For a caller-established decimal mean convention, `rounded_mean` accepts
`values` and `digits`, interprets each input's shortest decimal representation,
and averages before rounding half-away-from-zero. For example, the synthetic
request `{"operation":"rounded_mean","values":[0.11,0.12],"digits":2}` returns
`rounded_mean=0.12`. Passing an already-computed binary mean loses that protection.
This is not a general Excel engine or automatic input cleanup: extraction noise,
prior rounding, SD precision, and later arithmetic still need their own basis.

## Transport and result evidence

The CLI returns JSON on stdout, or an error on stderr with exit code 2 for
invalid requests. Unknown fields and nonnumeric observations are rejected, not
silently discarded. A CLI request array fails as a whole if any item is invalid.

Could an apparent tool failure be an input transport problem? In a pipeline to
`python3 -`, a heredoc supplies Python source on stdin and displaces the piped
JSON. Direct `--describe`, a request file, or an imported call avoids that
collision; it is not evidence that the numerical operation is unavailable.

Which extracted observations, conventions, returned values, and source
comparisons support the report's recalculation claim? Help output and synthetic
examples demonstrate an interface, not a review of the supplied data. A useful
tool result remains associated with the caller's evidence and identity when it
becomes a report finding.
