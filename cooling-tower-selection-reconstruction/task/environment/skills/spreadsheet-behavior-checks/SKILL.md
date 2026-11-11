---
name: spreadsheet-behavior-checks
description: Inspect workbook formulas and caches, recalculate with LibreOffice, and observe controlled input changes without judging domain correctness.
---

# Spreadsheet Behavior Checks

Formula text and cached display values are different evidence. Recalculate a
copy before interpreting its results. Use the helper for mechanical inspection;
the business model determines which inputs and results matter.

```sh
python /harbor/skills/spreadsheet-behavior-checks/scripts/workbook_tools.py \
  inspect --input MODEL.xlsx --report /tmp/inventory.json
python /harbor/skills/spreadsheet-behavior-checks/scripts/workbook_tools.py \
  recalc --input MODEL.xlsx --output /tmp/calculated.xlsx --report /tmp/recalc.json
python /harbor/skills/spreadsheet-behavior-checks/scripts/workbook_tools.py \
  scenario --input MODEL.xlsx --changes /tmp/changes.json \
  --watch /tmp/watch.json --report /tmp/scenario.json
```

Changes are records with `sheet`, `cell` and `value`; watches are `Sheet!A1`
locators. Select them from your own model. The script preserves the input and
reports observed differences; it contains no task formulas or expected answers.
Use `--allow-formula-inputs` only when a selected supplied input is itself an expression.
Keep diagnostic files outside the final deliverable directory. Use the actual
registered Skill directory if the harness mounts it somewhere else.
