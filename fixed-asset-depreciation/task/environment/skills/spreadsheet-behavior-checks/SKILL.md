---
name: spreadsheet-behavior-checks
description: Inspect spreadsheet formulas and caches, recalculate with an installed Office engine and measure controlled changes without modifying the source workbook.
---

# Spreadsheet behavior checks

A formula, its cached value and a real recalculated result are different evidence.
Use [probe design](references/probe-design.md) to select meaningful observations
and interpret the results. Derive expected behavior from the business model.

`scripts/workbook_tools.py` provides inspection, native recalculation and paired
input-change measurements. It needs Python with openpyxl; recalculation also
needs an installed `libreoffice` executable, or an engine supplied with `--engine`.
Resolve the script path relative to this skill's actual installation directory.

```sh
python scripts/workbook_tools.py inspect --input MODEL.xlsx --report /tmp/inventory.json
python scripts/workbook_tools.py recalc --input MODEL.xlsx --output /tmp/recalculated.xlsx --report /tmp/recalc.json
python scripts/workbook_tools.py scenario --input MODEL.xlsx --changes /tmp/changes.json --watch /tmp/watch.json --report /tmp/scenario.json
```

Changes are a JSON list of objects containing `sheet`, `cell` and `value`.
Values are ordinary JSON scalars; `null` clears an input. Dates can be entered
as spreadsheet serial numbers with the existing date formatting, using the
workbook's actual date epoch. Watches are a JSON list of `Sheet!A1` strings.
Select input cells yourself; the helper rejects changes to formulas.

The helper preserves the source and records its hash. A scenario recalculates
both an unchanged base and a changed copy. It measures values and errors without
deciding business correctness. Store exploratory files outside final output.

Office conversion can rewrite workbook features. Review layout, charts and other
required features before adopting a converted workbook as the deliverable.
Recalculate after the last edit and reopen that exact final file; another
openpyxl save can invalidate formula caches again.

