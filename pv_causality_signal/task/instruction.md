# Longitudinal safety-signal adjudication

The safety team needs a decision-ready review of the drug-event candidates defined below across the two reporting periods in the FAERS tables. The review must distinguish patients from follow-up submissions, show how reconciliation changes each candidate, test whether the canonical result persists across reporter and period views, and provide the adjusted reporting association needed for triage. The underlying tables are relational, so child records must stay attached to the correct submitted version and repeated drug or reaction rows must not become extra observations.

Candidate scope (`pair_id: active ingredient | exact event preferred term`):

```text
S01: TIRZEPATIDE | Diarrhoea
S02: PALBOCICLIB | Death
S03: PALBOCICLIB | Rash
S04: RIBOCICLIB | Headache
S05: PALBOCICLIB | Product use issue
S06: RIBOCICLIB | Arthralgia
S07: RIBOCICLIB | Nasopharyngitis
S08: RIBOCICLIB | Insomnia
S09: PALBOCICLIB | Cholelithiasis
S10: DAPAGLIFLOZIN | Dry mouth
S11: SEMAGLUTIDE | Haematocrit decreased
S12: ABEMACICLIB | Stomatitis
S13: RIBOCICLIB | Vision blurred
S14: DAPAGLIFLOZIN | Euglycaemic diabetic ketoacidosis
S15: SEMAGLUTIDE | Pancreatitis
S16: EMPAGLIFLOZIN | Diabetic ketoacidosis
S17: TERIPARATIDE | Alopecia
S18: EMPAGLIFLOZIN | Pneumonia aspiration
```

For each candidate, provide auditable four-cell tables, reporting odds ratios with lower confidence limits, signal calls, the effect of reconciliation, and an operational disposition. Exposure requires a `PS` drug role and a whole `prod_ai` component after splitting only on the documented backslash delimiter; no other drug role is exposed. The accepted component mapping is: each named ingredient maps to the identically named component, with `TERIPARATIDE ACETATE` also accepted for TERIPARATIDE and `DAPAGLIFLOZIN PROPANEDIOL` also accepted for DAPAGLIFLOZIN. Reporter groups are `HCP` for `MD`, `PH`, or `HP`, `CONSUMER` for `CN`, and `OTHER` for every other or blank occupation code.

Cover the canonical case population, the all-submission sensitivity, the canonical healthcare-professional population, each retained source-period population, and all six mutually exclusive retained period-by-reporter strata. Include sparse strata rather than silently dropping them. Use a two-sided 95% log-Wald interval without a continuity correction. A table with a zero cell is unassessable. Otherwise, a signal requires at least three exposed-event reports and a lower confidence limit above one. Escalation requires a canonical signal supported either by the healthcare-professional view or by both retained period views; other canonical signals remain under monitoring and candidates without a canonical signal are closed. An adjusted Mantel-Haenszel point estimate across the six strata is context, not a substitute for the signal rule.

Support the reconciliation conclusions with a closed version-driver census and a focused evidence register. For every candidate, census all multi-submission cases and report how many change primary-suspect exposure or target-event presence, how many change pair membership, how many change a table cell without changing pair membership, and how many return to an earlier state after an intervening change. Review these candidate-case combinations in detail:

```text
S01: 18263300, 23203180       S02: 14392010, 22518080
S03: 18671410, 20559130       S04: 12991330, 23326070
S05: 16886720, 19816840       S06: 14762680, 21118690
S07: 18372880, 18605850       S08: 16886720, 16900590
S09: 23274690, 23331050       S10: 16886720, 23267270
S11: 23028790, 23145750       S12: 16886720, 23293150
S13: 22839700, 23086130       S15: 23072320, 23315650
S16: 22923210                 S17: 18671410, 19611460
S18: 22790550, 23224460
```

For each selected combination, carry every submitted report identifier and numeric version, its exposure and event membership, its resulting pair state, the material additions or removals, and resolvable source rows. A state that later returns to its earlier value must still remain in the register.

The following retained reports need structured-only individual causality assessments (`review_id: primaryid | suspect active ingredient | exact event preferred term`):

```text
R01: 232616901 | EMPAGLIFLOZIN | Urinary tract infection
R02: 234512701 | EMPAGLIFLOZIN | Diabetic ketoacidosis
R03: 234844501 | SEMAGLUTIDE | Pancreatitis
R04: 233366401 | SEMAGLUTIDE | Intestinal obstruction
R05: 227626203 | ABEMACICLIB | Alopecia
R06: 1249156023 | PALBOCICLIB | Alopecia
R07: 236683601 | ABEMACICLIB | Erythema multiforme
R08: 236260101 | CANAGLIFLOZIN | Necrotising fasciitis
R09: 235543601 | DAPAGLIFLOZIN | Diabetic ketoacidosis
R10: 230196701 | ABEMACICLIB | Aspartate aminotransferase increased
R11: 231404201 | EMPAGLIFLOZIN | Ketoacidosis
R12: 180491904 | PALBOCICLIB | Condition aggravated
```

Preserve partial-date precision, distinguish unknown from negative findings, link therapy to the correct drug sequence and role, keep case-level recurrence evidence at its documented scope, and state the evidence that limits each final category. Each assessment must carry resolvable source-row references.

These case histories need a separate follow-up review (`change_id: caseid | suspect active ingredient | exact event preferred term`):

```text
L01: 22282990 | RIBOCICLIB | Headache
L02: 23347080 | DAPAGLIFLOZIN | Dry mouth
L03: 23299760 | RIBOCICLIB | Death
L04: 23302210 | PALBOCICLIB | Product use issue
L05: 23285260 | DAPAGLIFLOZIN | Diabetic ketoacidosis
L06: 23309310 | PALBOCICLIB | Anaemia
L07: 22889860 | ABEMACICLIB | Urinary tract infection
L08: 22967360 | PALBOCICLIB | Constipation
L09: 23090300 | PALBOCICLIB | Pneumonia
L10: 23337830 | PALBOCICLIB | Chest discomfort
L11: 23320410 | PALBOCICLIB | Granulocyte count decreased
L12: 23199360 | ABEMACICLIB | Vision blurred
```

For each version, record whether the requested primary-suspect product and target event form the pair, identify material additions, removals, or contradictions in chronology, withdrawal, re-exposure, role, or event evidence, and state whether the later submission changes pair membership, assessability, or the defensible causality conclusion. A later version number alone is not evidence of a stronger relationship.

Deliver one concise English JSON file at exactly `/workspace/faers_adjudication.json`. Its top level must contain `universes`, `pair_assessments`, `version_driver_assessments`, `case_assessments`, `longitudinal_assessments`, `method`, and `limitations`. Immediately after parsing the requested scope, create a valid JSON file with all required top-level keys, then update that file as each analysis stage is completed; do not defer the deliverable write until the end. Include every requested pair and review exactly once; do not reproduce source tables, file inventories, or hashes. The workspace contains only original report-source tables and their official data-format documentation; these are evidence inputs, not methods, answers, or worked examples. Methodology is available only through installed skills, and no file under `/workspace` is a method document. The supplied workspace is read-only, network access is unavailable, and every conclusion must rely only on materials under `/workspace`.

Check what is already available before you start. Before analyzing the data, invoke and apply every installed skill that is relevant to this pharmacovigilance review, including its closure checks.
