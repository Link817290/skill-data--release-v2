---
name: review-environmental-acceptance
description: Review environmental acceptance dossiers against project approvals, monitoring evidence and applicable technical rules. Use for cross-document reconciliation, defensible calculations, annotated reports and proportionate requests for missing evidence; not for certifying a site or inventing monitoring.
---

# Review an acceptance dossier

Establish the reviewed phase, historical period and supplied-document boundary.
Separate observations, source assertions, recalculations and reviewer conclusions.

1. Build a requirement → source/asset → monitoring event → operating-evidence
   chain using [evidence links](references/evidence-links.md). Validate identities
   and date coverage before accepting a whole-period assertion.
2. Use [measurement decisions](references/measurement-decisions.md) for units,
   censoring, averaging, normalized concentrations, paired mass flows and annual
   inference. Select the applicable rule before performing a compliance test.
3. Use [review disposition](references/review-disposition.md) to calibrate claim
   strength, request targeted records and attach comments to the actual issue.
   Preserve the original measured observations when the task is annotation.
4. Challenge each broad conclusion with one plausible missing-scope or
   alternative-interpretation case. A result may support a numerical comparison
   without establishing a valid campaign or acceptance readiness.

`scripts/review_checks.py` performs explicit-unit rate/load arithmetic, checked
pair efficiency and process/date coverage joins. Its examples and limits are
in the measurement reference. `scripts/read_word_comments.py DOCUMENT --out JSON`
checks saved comment text and anchors; neither tool decides legal compliance.

Stop short of the affected conclusion when identity, applicable criterion,
measurement validity or material coverage is unresolved. State what is known,
which record can close the gap, and which decision awaits it. Do not turn a
missing appendix into a nonexistent permit or a data gap into proven noncompliance.
