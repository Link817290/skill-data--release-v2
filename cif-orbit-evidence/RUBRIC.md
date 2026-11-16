# Scoring Rubric

The supplied CIF bytes and their source-derived facts are authoritative. P01-P11 are deterministic scientific arithmetic/source-pointer checks. A required source-bound semantic judge separately checks open scientific claim scope, evidence interpretation and source fidelity; it never rejudges affine/group/formula arithmetic. Equivalent numeric expressions and supported aliases retain credit. Unknown source values stay null with their reason visible.

Strict score is `sum(weight * completion) * retention`. Weights and deductions are in `task/tests/scoring_params.json`.

| Item | Weight | Checks |
| --- | ---: | --- |
| P01 Manifest | 0.02 | Exact supplied filename set (70%) and count (30%). |
| P02 Metadata | 0.18 | Per record: source path, atom-loop row count, operation count, raw space-group number, operation-loop completeness. |
| P03 Site identity | 0.05 | Per site: representative label, member labels, source rows, raw representative coordinates, reduced representative coordinates and element/fallback provenance. |
| P04 Site conclusions | 0.10 | Per site: orbit size, stabilizer order and general/special/unknown classification. |
| P05 Operation evidence | 0.12 | Per record: full ordered affine inventory, ordered-pair composition witness, mean complete per-site operation trace. |
| P06 Invariants | 0.10 | Per site: closure check and supplied multiplicity (explicit not-supplied state when absent). Integer closure is exact. |
| P07 Formula | 0.05 | Per record: status, derived totals, expected totals, unknown rows, raw formula, all formula-tag inventory/relation, and contribution ledger completion. |
| P08 Pointers | 0.15 | Per site: atom rows, operation ids and positive finite coordinate tolerance no wider than source-derived reference precision. |
| P09 Group | 0.08 | Per record: identity, determinants, operation orders, fixed-site profile, classes/histograms, signature and status, with supporting per-operation evidence. |
| P10 Comparison | 0.12 | Partition and status plus, for each of six pairs, same-signature conclusion, left operation ids and right operation ids. Each check earns equal partial credit. |
| P11 Reporting | 0.03 | Schema version (20%), record set (20%), record statuses (20%) and aggregate counts (40%). |

Per-site checks average within each record, then across the four files. Missing records contribute zero to their dimensions. P09 is all-or-nothing per record. Missing/extra site entries lose the affected record's site dimensions and trace component. P07 ledger checks each source row's site binding, line, label, raw and normalized element, fallback, raw/parsed occupancy, orbit size, contribution and status, plus row coverage and sum-to-total closure. Unknown or conflict rows require a nonempty reason; supported rows may omit it or leave it empty. No missing value is filled from a presumed chemical model.

Manifest and schema/index credit is multiplied by the mean record-content completion divided by 0.7, capped at one. This only discounts unsupported indexes. A wrong site classification loses its own P04 credit; it does not invalidate independent correct records, source facts or pointers.

## Equivalents

Leaf aliases are resolved by evidence role. Comparative arrays accept `pairwise`, `pairwise_comparisons`, `pairs`, `pairwise_audit` or `comparisons`; left/right files accept `left_file`/`left`/`file_a`/`a`/`record_a`/`first`/`left_record` and corresponding right aliases. Reversing files is valid only with the corresponding evidence sides reversed. Evidence ids must belong to the named source side.

Numbers accept finite integers, decimals, numeric strings, fractions such as `1/1000`, and documented exact/decimal wrappers in operation fields. Coordinates compare within 1e-6; affine values and formula counts within 1e-9. Orbit sizes and stabilizer orders remain exact integer facts. NaN, infinity, invalid fractions and booleans are not numerical evidence. Site ids and site/record ordering are free; sites match by representative label or source rows. Contribution containers accept `contribution_ledger`, `contributions` or `row_contributions`; common row/line/label/type/occupancy/contribution aliases are resolved. Unknown and conflict reasons may be concise codes; no prose length is scored.

Supported/consistent/closed/holds/complete/true statuses are normalized; conflict/inconsistent/violated/false and unknown/undetermined/unresolved are similarly normalized. Optional absent tags require explicit absence without invented values. Composition pairs accept usual separators or left/right/product objects. Dictionary order and explicit zero histogram classes are immaterial.

Occupancy tolerance is the per-element sum of orbit size times half the last reported occupancy decimal unit; exact 0/1 occupancies contribute zero. This actual budget is used for formula comparisons. Beta's Fe/Os residuals are 0.02 within 0.12 budgets. Coordinate tolerance does not relax discrete integer closure.

## Deductions

| Item | Coefficient | Trigger |
| --- | ---: | --- |
| D01 | 0.1 | Once if any live supplied CIF is missing or its SHA-256 differs. |
| D02 | 0.65 | Once for formula status contradicting its own totals/tolerance or pair conclusion contradicting its own partition. |
| D03 | 0.8 | Once for missing or unusable required register evidence units, listing every affected unit. |
| D04 | 0.8 | Once when open narrative conclusions exceed supplied CIF evidence/applicability or misstate what pointers/signatures establish. |

The coefficients are retained-value factors. D01 retains `0.1` because a
missing or changed issued CIF nearly destroys provenance for every derived
claim. D02 retains `0.65` because a contradiction between a conclusion and its
own recomputable totals or partition materially damages scientific trust, while
unaffected records remain useful. D03 retains `0.8` because missing evidence
units are locally repairable and already lose their positive owner credit; the
additional 20% reflects register-level audit incompleteness without charging
each missing unit again. These values express provenance and scientific-
consistency consequences, not observed model scores or a pass-rate target.

Required units include all records and nonempty source-bound sites, each site's orbit size, stabilizer, classification, closure, supplied multiplicity, coordinate evidence and operation trace, complete affine/composition inventories, operation group, formula reconciliation with contribution ledger, mandatory source states, manifest, anchored comparisons and aggregate. A present unit with a wrong source binding, invalid mandatory invariant or non-recomputable evidence is unusable for completion and is treated like an omission. Affected units also lose their applicable dimension credit. Independent affected units do not multiply D03 repeatedly. Integer arithmetic and mandatory scientific conclusions remain required.

D04 is a local semantic-scope retention: numerical/group owners keep their
native scores, while unsupported external phase/compound/causal claims retain
80% of otherwise valid work. The required semantic IDs are `source_fidelity`,
`conclusion_scope` and `evidence_interpretation`; all must be 1 for lenient.
Judge failure is infrastructure UNMEASURED, never candidate zero.
The required semantic layer uses OpenAI Responses with `stream:false`, low reasoning,
a compact strict JSON schema and defensive completed-response/SSE validation.

## Completion

`reward_lenient` is binary and independent of strict weights: the register must cover the input files and all required evidence units, have correct site identity and scientific conclusions, complete operation/group evidence, correct formula ledgers and source pointers, and recomputable statuses/aggregate. Comparative completion requires the correct partition, status and all six pair conclusions, with at least one correctly side-bound operation anchor per pair; strict P10 still scores both directional pointers separately. Because each named record must already carry its complete operation and group evidence, the opposite pointer is recomputable, so one omitted navigation pointer is a strict-quality loss rather than a completion failure. A pair with neither valid anchor, wrong-side anchors or a missing/incorrect conclusion fails completion. Redundant source-count metadata and schema-version formatting affect strict quality but do not independently block business completion. Any source tampering, scientific contradiction or missing core required unit fails completion. Lenient is never calculated from a strict-score threshold. `reward` aliases strict; reward files contain numbers only, with details separate. Invalid/non-object JSON scores zero; scorer infrastructure failures fail nonzero and clear stale rewards.
