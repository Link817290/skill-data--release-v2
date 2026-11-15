---
name: evidence-based-test-design
description: Build executable integration test workbooks from product specifications and procedures, reconcile source authority and verify saved cases against observable effects and measurement contracts.
---

# Evidence-Based Integration Test Design

All product facts come from the supplied inputs. Keep working artifacts outside
the final-output directory. Deliver the requested workbook with unexecuted
results unless actual run evidence was supplied.

## Read sources and choose the scope

Run `scripts/extract_sources.py MATERIAL_DIRECTORY --output WORKING/sources.json`.
Read neighboring paragraphs and table rows around relevant hits. Inspect figures
when extracted text does not express their content.

Create a short coverage map of the requested functions and quality constraints,
their controlling source locations and planned case identifiers. Group related
statements into testable behaviors rather than cataloguing every sentence.
Keep incidental product specifications outside the plan unless they affect a
requested case's fixture or verdict. Prioritize completing executable cases.

Read [references/case-closure.md](references/case-closure.md) before writing cases.
For conflicting statements, first compare endpoint, configuration, quantity and
starting event. A defect-severity example classifies a failure; it does not set
a passing limit. Preserve unresolved same-scope branches in the affected case.
The detailed [decision ledger](references/decision-ledger.md) and its auditor
are optional for difficult conflicts; a separate exhaustive JSON ledger is not
required. Record decisions in the workbook where they affect execution.

## Write complete cases into the deliverable

Each case needs an effective fixture, controlled trigger, observable response,
source-grounded verdict and restoration. Establish paired/configured/active
state explicitly; possession of equipment does not establish operating state.
Include the functional effect even when the case also measures performance.

Shared setup and measurement cases may be linked by identifier. State which
configuration and method are inherited, and keep the scenario's distinctive
trigger, physical response and verdict in its own row. Do not let a generic
measurement reference stand in for the scenario's behavior.

For quantitative checks read
[references/measurement-contracts.md](references/measurement-contracts.md).
Bind each quantity to its own endpoint, observable events, units, statistic,
threshold and source. A command acknowledgement cannot prove physical response.
Authored stimulus counts, load profiles and sampling choices establish a method,
not a new product promise. Unsupported behavior is observed without an invented
pass/fail threshold. A conditional requirement still needs a runnable supported
branch and evidence needed to resolve the conditional verdict.

## Review the saved workbook

Run after saving, then read the exported cases rather than the generation code:

```bash
python /path/to/skill/scripts/audit_plan.py PLAN.xlsx --sources WORKING/sources.json --output WORKING/saved-review.json
```

The report includes actual saved row content and cell locations, structural
findings and a focused review queue. If dedicated source, source-location and
quote columns exist, the tool also checks quotes against extracted records.
It imposes no column layout. Review source notes manually when stored elsewhere.
The report is advisory: it does not interpret product facts or certify coverage.

Trace the short coverage map forward to actual rows and each expected result
back to its source. For every case, mentally execute setup, trigger, observation
and verdict using only saved cells and explicit dependencies. Correct the
workbook, resave and rerun once changes are complete. A correct working ledger
does not establish that the delivered workbook is correct.
