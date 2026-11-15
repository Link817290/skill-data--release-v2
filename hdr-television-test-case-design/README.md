# LG OLED65C22LB HDR Function Test Design

This SkillsBench task asks an agent to produce an English HDR function test item workbook for the LG OLED65C22LB from a product specification, an HDR technology guide, project acceptance requirements, and an SMW200A getting-started manual.

## Task package and output

- Agent-visible inputs are under `task/environment/workspace/`.
- The blank workbook is the delivery template.
- The expected output is an English XLSX workbook containing identifiable Test ID, Test Module, Test Case Name, Preconditions, Test Steps, and Expected Result fields.
- The expert-confirmed reference workbook is under `golden/` and is not agent-visible during evaluation.

## Scoring

`task/tests/validator.py` uses task-specific relation groups rather than row IDs or exact prose. It scores the nine expert-confirmed HDR objectives, five project acceptance relationships, evidence and equipment roles, executable procedures, expected-result closure, and the English workbook. The six published dimensions are additive; missing work loses its own credit and unique source-bound errors are deducted without a score cap or coverage multiplier. Row order, a defensible split or consolidation, and semantically equivalent English wording do not affect credit.

The expert Gold receives strict reward `1.0`. This is a local scorer check, not a model-evaluation result.

## Source sufficiency note

The supplied LG document supports the target television's HDR format capabilities, the HDR guide supports general HDR concepts, and the project acceptance document supplies the approved measurement conditions and acceptance values. The supplied SMW200A manual does not establish an HDMI display-pattern source or photometric/colorimetric measurement chain. The Golden therefore uses a qualified HDMI HDR pattern generator and separate calibrated photometer/colorimeter roles without inventing SNW200A functions.

## Reproduction

Build the actor and verifier from `task/environment/Dockerfile` and `task/environment/Dockerfile.verifier`. Run the Oracle with `task/solution/solve.sh OUTPUT_DIR` and the scorer with `task/tests/test.sh OUTPUT_FILE`. The exact Golden semantic result is available in packaged replay mode. New candidates use the six externally supplied `LLM_JUDGE_*` settings.

Both conditions use the same source workspace and scorer; only the with-skill condition exposes `task/environment/skills/`.
