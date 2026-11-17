# Structural calculation review rubric

## Scoring summary

The scored deliverable is `/workspace/review.xlsx`. The verifier combines direct workbook inspection with mandatory source-bound semantic adjudication by `gpt-5.6-sol`. It reports two co-equal lenses:

`reward_strict = 0.04 * load_arithmetic + 0.07 * stability_scope + 0.06 * serviceability_limit_application + 0.20 * reinforcement_demand_boundary + 0.55 * approval_chain_reproducibility + 0.05 * evidence_binding + 0.03 * workbook_closure`

`reward_lenient = 1.0` only when semantic coverage, traceable matched rows, all necessary PASS/FAIL/REVIEW conclusions, unresolved-state preservation, calculation-row formulas, and workbook usability are complete; otherwise `0.0`.

`reward` is the compatibility alias for `reward_strict`. The reference workbook scores 1.0000 under both lenses. The strict score is continuous; the lenient lens is a binary delivery-contract check.

Rows are aligned to report-supported checks by source-bound meaning. Equivalent professional wording and a conclusion distributed across several rows are accepted. A particular identifier, column title, sheet name, row order, or sentence is never required. Formula-backed status cells are recalculated on an isolated workbook copy before the adopted status is scored.

## Capability dimensions

### Load arithmetic

- **Weight:** 0.04
- **Capability:** Preserve action direction and units while reconstructing force and moment relationships.
- **Professional reason:** Uplift, downward force, and signed moments can look arithmetically plausible after a sign or subtotal error.
- **Anchor type:** `numeric_derivation`, `relation`, `source_location`.
- **Verifier signal:** Correct status on the force-subtotal and signed-moment relationships after semantic row alignment.
- **Attention role:** Connect component actions to their reported resultant; ignore favorable narrative summaries that do not establish arithmetic closure.
- **Accepted variation:** Equivalent formulas, intermediate columns, rounding displays, or row descriptions.

### Stability scope and case-specific limits

- **Weight:** 0.07
- **Capability:** Compare stability and bearing results with the allowance applicable to the same load case, while distinguishing a dash from zero or demonstrated compliance.
- **Professional reason:** A nearby allowance can be misapplied, and an omitted factor can be incorrectly promoted to a passing result.
- **Anchor type:** `relation`, `enum_status`, `source_location`.
- **Verifier signal:** Correct conclusions for the supported factor and stress comparisons and for the unresolved applicability entry.
- **Attention role:** Attend to the table row and adjacent scope text; connect each calculated factor to its own allowance; ignore blanket statements that the structure satisfies requirements.
- **Accepted variation:** A reviewer may aggregate several cases in one row when the numeric evidence remains traceable.

### Serviceability limit application

- **Weight:** 0.06
- **Capability:** Bind crack-width and deflection results to the member category, environment statement, and limit actually supplied in the report.
- **Professional reason:** The most generous limit in a calculation book is not automatically applicable to every beam, slab, wall, or pier.
- **Anchor type:** `relation`, `numeric_derivation`, `source_location`.
- **Verifier signal:** Correct serviceability conclusions whose evidence aligns the observed values with the applicable report provisions.
- **Attention role:** Connect result tables to the cited serviceability section and material/environment statement.
- **Accepted variation:** One row may cover a homogeneous member series; individual member rows are equally valid.

### Reinforcement demand boundary

- **Weight:** 0.20
- **Capability:** Distinguish a shown bar arrangement, a mechanically computed provided area, and a demonstrated capacity comparison; preserve `REVIEW` when demand or provided reinforcement is missing.
- **Professional reason:** The common expert error is to call reinforcement adequate because bars are listed, even though the calculation book never supplies both sides of the comparison on the same basis.
- **Anchor type:** `enum_status`, `relation`, `expert_judgment_record`, `source_location`.
- **Verifier signal:** Correct unresolved judgments for the report's demand-only and arrangement-only evidence groups.
- **Attention role:** Connect location, face, strip basis, provided steel, and required steel; ignore unstated code defaults or demand borrowed from another member.
- **Accepted variation:** Bar areas may be shown by Excel formula or an equivalent transparent calculation, but a computed area alone does not resolve an absent demand.

### Approval-chain reproducibility

- **Weight:** 0.55
- **Capability:** Decide whether an approval conclusion is closed by the supplied evidence, keeping a displayed factor-to-limit comparison separate from the ability to reproduce the factor or its governing applicability.
- **Professional reason:** Calculation books often expose final factors and favorable summaries while omitting the actions, coefficients, exposure assignments, or resistance inputs that make those results independently checkable.
- **Anchor type:** `relation`, `invariant`, `expert_judgment_record`, `source_location`.
- **Verifier signal:** Correct conclusions for overall approval, reproducibility of each stability family, serviceability-to-member assignment, narrative-versus-row conflict, and a linked blocker disposition.
- **Attention role:** Connect the structural tables, their scope paragraphs, serviceability provisions, and unresolved reinforcement/anti-uplift evidence; ignore a favorable summary when its supporting chain is open.
- **Accepted variation:** A single summary row or a separate issue register is valid when it links the affected checks, source locations, and closure evidence without relying on fixed headings.

### Evidence binding

- **Weight:** 0.05
- **Capability:** Bind each conclusion to a report locator, observed value, governing basis, and finding.
- **Professional reason:** A technically plausible status without a resolvable evidence path cannot be independently checked or approved.
- **Anchor type:** `source_location`, `identifier`, `relation`.
- **Verifier signal:** Per-row locator, observation, finding, and numeric-anchor coverage after semantic matching.
- **Attention role:** Attend to source cells and section text; connect each cited value to the judgment it supports.
- **Accepted variation:** Page, printed-page, section, and table-row locators are accepted when they resolve to the supplied report.

### Workbook closure

- **Weight:** 0.03
- **Capability:** Deliver an inspectable workbook with visible formulas, a usable status legend, and no duplicate row identifiers.
- **Professional reason:** Review findings must remain usable after handoff and calculations must be distinguishable from typed conclusions.
- **Anchor type:** `invariant`.
- **Verifier signal:** Formulas at the applicable derived-calculation rows, an operational legend for PASS/FAIL/REVIEW and engineering units, and identifier uniqueness.
- **Attention role:** Connect mechanical workings to the review rows while keeping the original report unchanged.
- **Accepted variation:** Sheet names, styling, header synonyms, workbook order, and the formula column may differ when each formula remains visibly bound to its applicable calculation row.

## Skill-attributable contrast

**With-procedure profile:** The workbook systematically preserves dash/blank/zero distinctions, reconstructs signed relationships, applies member-specific serviceability limits, keeps demand-only reinforcement checks unresolved, and binds every conclusion to original report evidence.

**Ad hoc profile:** A competent reviewer usually records the prominent factor and serviceability comparisons, but may accept the report's favorable summary, treat bar marks as proof of adequacy, omit demand-only rows, or cite a table without preserving the values that support the conclusion.

The dimensions most attributable to the supplied procedures are stability scope, serviceability limit application, reinforcement demand boundary, approval-chain reproducibility, and evidence binding. They correspond respectively to the skills' scope/non-applicability, serviceability and demand-side, two-layer conclusion, and review-universe/closure sections. Format and naming are shared conditions and are not treated as evidence of method use.

## Robustness and anti-gaming

- Renaming sheets, using supported header synonyms, replacing row IDs, changing row order, and paraphrasing findings must leave a substantively equivalent workbook at 1.0000.
- A workbook containing only expected-looking IDs, a number dump, repeated generic findings, or a file with no review table cannot satisfy the headline dimensions.
- A single evidence row cannot be reused for several reference checks; source dumping therefore does not create artificial coverage.
- Wrong status decisions retain only limited evidence credit and cannot be hidden by polished prose. A formula-backed status is judged from its calculated result, not its formula text.

## Known limits

The package evaluates the review boundaries evidenced by the supplied report; it does not claim a fresh structural design, independent finite-element analysis, or exhaustive compliance with standards absent from the materials. The score is suitable for comparing evidence-bound review behavior, while external release decisions require the archived rollout and process-audit evidence.

Wing-wall reinforcement may be established jointly by several detailed checks. Stability comparison and independent reproduction are separate evidence layers; common numbers never substitute for the correct layer. All professional conclusions use mandatory evidence-bound semantic adjudication with exact candidate spans. The required judge uses the OpenAI Responses protocol, `gpt-5.6-sol`, and verifier-only endpoint and credential variables. Judge, schema, or formula-calculation infrastructure failure produces no score.
