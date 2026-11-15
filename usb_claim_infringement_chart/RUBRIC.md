# USB Claim Infringement Chart Rubric

## Authority and Measurement

The executable authority is `task/tests/test.sh`, `validator.py` and
`mix_judge/apply_semantic.py`. Deterministic checks own identifiers, coverage,
record shape, enums and directly computable relationships. The source-bound
`gpt-5.6-sol` review owns open claim meaning, evidence roles, reasoning coherence
and professional equivalence. Missing or invalid judge evidence is an
infrastructure state and publishes no candidate score.

The only graded artifact is `/workspace/claim_chart.json`. A deterministic scorer compares that JSON against the reference record in `tests/ground_truth.json`; it does not read how the file was produced, the prose style, or which supporting material was available. Scoring evaluates the substance of each determination, not wording, field order, or container shape. `reward` aliases the strict score; a separate lenient lens asks whether counsel received a complete, calibrated brief.

## Score Form

Program strict is `sum(weight[P] * register_core[P]) * systematic_inversion_factor * blanket_call_retention`.
Weights come from `tests/scoring_params.json` and sum to 1. A missing or incorrect record reduces its own register's core. Coverage and terminal-call accuracy are not shared multipliers. The systematic-inversion factor is the existing normalized inversion detector; blanket-call retention is 0.1 only for D01, otherwise 1.

Final strict is `0.90 * program_strict + 0.10 * semantic_score`, except the
unchanged Golden remains exactly 1 when both components are 1. The semantic score
is the equal mean of claim meaning, evidence binding, reasoning coherence and
scope calibration. This share is limited to open professional interpretation;
it does not regrade deterministic IDs, enums or arithmetic.

| Item | Register | Weight |
| --- | --- | ---: |
| P01 | Published comparisons | .20 |
| P02 | Same-number version mapping | .13 |
| P03 | Evidence bridges | .15 |
| P04 | Construction dependencies | .08 |
| P05 | Sensitivity | .07 |
| P06 | Dependency audit | .12 |
| P07 | Family correspondence | .10 |
| P08 | Issued comparisons | .15 |

Register cores use the following terms, each averaged over its own expected records:

- Published: .45 terminal calls + .40 feature classes + .15 evidence binding.
- Mapping: .45 feature-set similarity + .25 lineage similarity + .30 scope-relation accuracy.
- Issued: .25 terminal calls + .45 feature classes + .15 decisive-feature similarity + .15 evidence binding.
- Bridges: .65 linked determination + .20 affected-feature similarity + .15 evidence/reason completeness.
- Construction: .60 disposition + .20 affected-claim similarity + .20 affected-feature similarity.
- Sensitivity: .65 linked determination + .25 decisive-feature similarity + .10 reason completeness.
- Dependency: .10 printed parent + .60 linked dependency determination + .25 coherent-parent candidate + .05 locator/reason completeness.
- Family: .25 destination similarity + .30 inherited-feature similarity + .25 correspondence status + .15 dependency effect + .05 locator/reason completeness.

Set terms use Jaccard similarity and normalized categorical terms use exact classifications. Family inherited-feature credit is scaled by destination similarity; issued decisive-feature credit is scaled by that comparison's feature accuracy. Related bridge, sensitivity and dependency columns are evaluated as a linked determination. Evidence completeness is assessed within its register and is not multiplied by unrelated terminal calls.

The published workstream covers eight target/claim comparisons and 42 findings; issued work covers ten comparisons and 94 findings, with six same-number mappings, 15 dependency rows, seven family rows, and the designated bridge/construction/sensitivity rows.

### Accepted equivalent expressions

- Collections may be lists or identifier-keyed objects, and rows and findings are resolved by identifier rather than order, headings or prose. Reordering every array, using a keyed collection, or adding explanatory fields does not change a correct score.
- Documented container aliases are accepted: `published_comparisons` for `comparisons`, `claim_version_impact` or `version_analysis` for `version_impact`, `issued_comparisons` for `granted_comparisons`, `claim_deltas` or `claim_mappings` for `same_number_claims`, `bridge_assessments` for `evidence_bridges`, `claim_construction_issues` for `construction_dependencies`, `outcome_sensitivity` for `sensitivity_matrix`, `claim_dependency_audit` for `dependency_audit`, and `claim_family_correspondence` for `family_correspondence`.
- Documented field aliases are accepted, including `overall` or `verdict` for `terminal_call`, `status` or `classification` for `evidence_class`, `bridge_status` for `link_status`, `scenario_call` for `hypothetical_call`, `policy` for `expansion_policy`, and `evidence_ids` or `sources` for `source_ids`.
- Versioned claim references are matched after version-prefix normalization wherever they are compared, in the dependency audit and in the construction register's `affected_claim_refs`, so `PUBLISHED:12`, `PUB:12` and `pub-12` all denote the same claim.
- Row and finding identifiers are matched after surrounding whitespace is trimmed; a blank identifier registers nothing, and a duplicate identifier is ignored after the first occurrence.

## Deductions and locality (2026-10-24)

D01 remains the 0.1 blanket-call penalty for >=90% identical definite calls. Ordinary local errors D02–D09 are represented once by the affected dimension's classification/relation correctness, without another global multiplier. Coverage loss remains local to its dimension. Only the existing systematic-inversion detector may affect all dimensions. Shared terminal-call correctness is no longer multiplied into unrelated dependency/family/bridge work.

Weights: P01 published comparison .20; P02 version mapping .13; P03 bridges .15; P04 construction .08; P05 sensitivity .07; P06 dependency .12; P07 family .10; P08 issued comparison .15. All computed substantive sections now receive explicit credit.

Issued-claim analysis may cite PAT_APP descriptive evidence alongside its required target and controlling sources; this does not replace issued claim text or scope mapping. ON_DS Figure 1 p2 directly supports the four-conductor limitation 5.1, separately from actor/timing questions.

## Lenient Lens

A 0/1 lens is reported next to the strict score. It is 1 when all of the following hold: every one of the twelve coverage fractions is 1; each same-number mapping row carries a non-empty feature set, lineage and scope relation; `analysis_completeness` is 1 with a non-empty `assumptions_and_scope`; the blanket-call test passes; the terminal calls retain both `PASS` and `REVIEW` outcomes; and at least half of the reference `REVIEW` comparisons, rounded up, are recognised as such. Indiscriminate positive calls fail this lens. Otherwise it is 0.

## Substantive Standard

Published and issued claim sets are expanded independently. Same-number scope is determined from normalized limitation sets, and lineage includes every published claim that contributed required subject matter. Issued comparisons are recomputed feature by feature rather than carried over from the earlier analysis of the published application.

`DIRECT` means the target record itself supplies the proposition. `COMPOSITE` requires both a target-specific link and a mandatory proposition in a supplied reference. `NOT_SHOWN` is an unresolved evidence gap, not a contradiction. `CONTRADICTED` requires a target-specific mutually exclusive fact. A positive terminal call requires every feature to be directly or validly compositely established.

Actor, content, signaling path and event order remain distinct. A powered-device request is not charger-originated capability information. A commanded output change is not automatically a data message. A static voltage state is not automatically a pattern of toggles, equal line voltages do not alone prove a physical short, and a connector or protocol label does not establish every optional signaling method. A disclosed path does not exclude an additional path unless the record supplies an exclusivity premise, and statements tied to one regional or operating mode are not generalized to another without evidence.

Construction dependencies are separated from missing target facts. Intrinsic claim and specification text may resolve a proposed equivalence, reject it, or leave a question requiring construction. Sensitivity analysis changes only the stated hypothesis, retains every unrelated feature state, and then recomputes the claim result under the all-elements rule.

Dependency review preserves the parent number printed in each claim. A valid dependency is expanded through its own version's chain. A self-reference or category-inconsistent parent remains a visible defect and is not silently repaired. A candidate coherent parent may be identified from a parallel family or a semantic sequence, but it stays separate from the controlling expansion policy.

Family correspondence follows retained terminal subject matter rather than claim number. It distinguishes a renumbered dependent limitation from subject matter absorbed into a later independent claim, expands the issued destination through its actual parent, and preserves the effect of a broken published dependency. The semantic destination is review information, not a repair of the printed claim.

## Weight Rationale

Published and issued comparisons receive the largest shares because they contain
the substantive infringement determinations. Evidence bridges and dependency
audits receive the next shares because unsupported links can change a claim result
even when the terminal call looks plausible. Mapping, construction, sensitivity
and family correspondence remain separate to preserve the legal questions they
answer. Local register terms retain partial credit, so one incorrect relation does
not erase unrelated analysis.
