# Scoring Rubric

The primary `reward` combines a deterministic comparison with the user-designated Golden and a condition-blind semantic comparison against the same Golden portfolio.

## Factual-accuracy

Twenty evaluator-side checks compare each submission with a hash-bound structured contract derived from the four Golden DOCX files. Every check is binary (`0` or `1`); the weighted total is reported as `reward_factual_accuracy`.

| Group | Weight | Scope |
| --- | ---: | --- |
| M01-M08 | 37 | Required files, substantive multi-cell Word records, reusable template fields, neutrality, row-linked structural reuse, and correct case ownership |
| M09-M12 | 21 | CASE-001 Golden labels, values, units, ranges, time, and explicitly missing potassium |
| M13-M16 | 21 | CASE-002 Golden labels, values, units, ranges, report time, and recorded bradycardia diagnosis |
| M17-M20 | 21 | CASE-003 Golden analytes, all three result groups, units, ranges, dates, and handwritten times |

The structured contract is `task/tests/golden_contract.json`. Its Golden hashes must match `task/tests/ground_truth.json`, and the unchanged Golden must score `1.0`.

## Reasoning-quality

A blinded reviewer receives only the four Golden DOCX contents, the four submitted DOCX contents, and the machine rubric. It does not receive the source images, a source-fact ledger, the skill condition, or the execution trajectory.

Ten weighted dimensions contain forty binary semantic checks. Each dimension earns proportional credit for its passed checks. Golden-derived Factual-accuracy prerequisites remain visible as diagnostic misses but do not zero Reasoning-quality a second time.

| Group | Weight | Scope |
| --- | ---: | --- |
| B1-B2 | 16 | Reusable evidence and reasoning quality of the template |
| B3-B4 | 20 | CASE-001 diagnostic uncertainty, bounded interpretation, and follow-up |
| B5-B7 | 34 | CASE-002 diagnosis, severity, urgent risk handling, causal restraint, and workup |
| B8-B9 | 22 | CASE-003 time-specific interpretation, repeated evidence, and uncertainty |
| B10 | 8 | Portfolio consistency and professional usability |

The factual allocation gives 37% to file/template and cross-case ownership
controls because a case swap or contaminated reusable template compromises the
whole portfolio. Each of the three case records then carries the same 21%, so
one longer case does not dominate extraction fidelity. Within reasoning quality,
CASE-002 carries 34% because the documented bradycardia/hyperkalaemia pattern
requires the most urgent severity, safety and causal-restraint decisions;
CASE-003 carries 22% for time-specific repeated evidence, CASE-001 carries 20%
for bounded diagnostic uncertainty, the reusable template carries 16%, and
portfolio consistency carries 8%. Multiplying factual accuracy by reasoning
quality models a clinical dependency: sound interpretation must remain bound to
the correct patient facts, while partial performance in either layer remains
visible. It is not a score threshold or a hard cap.

The reviewer compares semantic substance rather than wording, language, row order, headings, or visual similarity. Every decision must cite one Golden and one submission span using structured origin and artifact-role fields. The evaluator verifies that both quotations are exact text from the declared DOCX role before accepting the review. A free-form claim that merely names Golden or Submission is not evidence.

The semantic layer uses one condition-blind reviewer rather than averaging repeated calls to the same model family. Independence is supplied by the separate 20-check deterministic factual layer and the exact paired-evidence contract; a second correlated model call would add variance without proving reviewer independence. Reviewer identity and limitations remain explicit in every accepted review.

## Lenient Must-have standard

The independent Lenient score is `1` only when delivery structure checks M01,
M02, and M06-M08 pass, at least two of M10, M14, and M18 pass, and the
source-bound semantic review confirms the critical diagnostic direction checks
B3.1-B3.3, B5.1, B5.2, B5.4, and B8.1-B8.3. This requires four readable,
editable records, a neutral reusable template, correct cross-case ownership,
usable source transcription in most cases, and no reversal of the core
diagnosis/severity/time-course conclusions. Lenient does not depend on a strict
score threshold or on matching Golden prose.

## Aggregation

- `reward_factual_accuracy = sum(factual-check weight * binary result) / 100`
- `reward_reasoning_quality = sum(reasoning item weight * passed checks / item checks) / 100`
- `reward_strict = reward_factual_accuracy * reward_reasoning_quality`
- `reward = reward_strict`
- `reward_lenient = 1` when M01, M02, M06-M08 pass, at least two of M10,
  M14, M18 pass, and all declared critical semantic checks pass; otherwise `0`

The multiplication preserves partial credit across factual extraction and reasoning quality. Lenient is reported independently and never caps or rescales the continuous score.

## Reference and replay

The active Golden was source-audited against the issued images and the
evaluator-side source-fact table. The single record under
`task/tests/golden_replay` contains that criterion-by-criterion reference review
and is bound to the Golden artifact hashes, rubric, factual contract, and
source-fact table. Golden passes through the same factual and aggregation code
as a submission; its hash match selects the bound review but does not create
automatic credit. Any unseen artifact set is evaluated against the same checks
by the condition-blind live model judge. Both reviewer kinds must return the
same complete evidence-bearing review schema.
