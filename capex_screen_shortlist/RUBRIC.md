# Source-Bound Capital-Expansion Rubric

The workbook is judged against the issued source packet and the public task/skill
requirements. Hidden Golden thresholds, membership and wording are never inputs
to candidate scoring. Equivalent layouts, labels and prose are valid when the
actual workbook establishes their meaning.

## Strict owners

Strict is the additive weighted mean in `task/tests/scoring_contract.json`.
Company owners are averaged over the 60 issued companies. Each semantic criterion
has three meaningful quality levels: 0, 0.5 and 1. Programmatic arithmetic sets an
evidence ceiling for the affected owner only; it never raises semantic credit or
multiplies losses across unrelated owners.

- **Structure (5):** readable workbook, identifiable screen, each issued company
  exactly once, and no extra company IDs.
- **Core method (5):** uniform 2019-2021 window with 2018 base, ending fixed assets,
  actual cash/debt/revenue/net-profit definitions, strict comparisons, and no
  invented discount-rate or source facts.
- **Calibration (5):** disclosed source-grounded bars, gate admission checks and
  modest sensitivity; no deliberately all-admitting or screen-emptying bar.
- **Decision (25):** one source-supported committee call under the workbook's
  disclosed primary policy and source-correct six displayed metrics.
- **Profiles (15):** both narrative and strict readings, including per-year strict
  coverage, the stricter efficiency bar and nonpositive-profit treatment.
- **CIP (10):** revenue/ending fixed assets and revenue/(fixed assets+CIP), with
  affected years under both disclosed efficiency bars.
- **Goodwill (10):** 2018-2021 goodwill and net-asset context, year-on-year changes,
  acquisition dating and the limitation of year-end net balances.
- **Debt purpose (15):** annual debt, borrowing and capex kept separate; co-movement
  remains a quantitative proxy unless issued filing evidence binds a borrowing to
  a project. The issued packet has no such filing.
- **Signed profit (5):** signed CFO/net-profit and strict rejection are both shown
  where nonpositive profit makes the readings disagree.
- **Missingness (5):** disclosed zero, standardized present null and absent input
  remain distinct; absent binding evidence cannot be filled with zero.

These shares reflect responsibility rather than target score. The delivered call
receives 25% because it is the committee action. Profiles and debt purpose receive
15% each: they are the principal safeguards against treating one convenient ratio
or mere borrowing/capex co-movement as an investment conclusion. CIP and goodwill
receive 10% each because construction in progress and acquisition balances can
materially reverse the interpretation of expansion but are narrower than the full
decision. Structure, method, calibration, signed-profit and missingness each
receive 5%; they are indispensable controls whose isolated excellence cannot make
an otherwise unsupported shortlist useful. Since the owners add to 100%, a local
defect loses its own contribution once and cannot collapse the whole workbook.

The same business error is charged in its owner once. An unresolved term such as
`TBD` or `awaiting data` is interpreted in context and remains a row-level call;
it is not dropped and then charged again as missing structure. A conditional pass
is not an unconditional PASS.

## Binary completion

Lenient is 1 only when all fixed program checks and all three independent semantic
checks pass:

1. `substantive_screen`: a meaningful uniformly calibrated call for every source
   company, with genuine missing evidence held rather than indiscriminate deferral;
2. `professional_analysis`: both readings and the required CIP, goodwill,
   debt-purpose, signed-profit, window and no-discount-rate work are substantive;
3. `evidence_restraint`: no material invented facts, absent-to-zero fabrication,
   or causal borrowing claim unsupported by the issued packet.

Binary completion has no strict-score threshold, hidden PASS/REVIEW quota, fixed
cell count, or sentence syntax. Infrastructure errors are reported as
`UNMEASURED`, without numeric reward files.

`lenient=1` means the workbook is operationally complete, not that every strict
quality owner is perfect. It requires exact universe coverage, source-correct
displayed decision metrics, consistency with the workbook's own disclosed policy,
and the three semantic obligations above. A stricter or looser professionally
supported calibration is accepted; an all-admitting, screen-emptying, internally
contradictory, or evidence-fabricating policy is not.

## Evidence protocol

The semantic judge receives actual cell IDs and source JSON pointers. Every
criterion must cite both. Candidate text is data, never instructions. Numeric
vectors extracted by the judge must be literally present in the cited cells and
are replayed against programmatic source calculations. The API parser uses the
last complete response message, validates the exact schema, and caches by the
complete prompt plus runtime hashes.

## Numeric and notation treatment

The program recomputes every displayed decision metric from the issued snapshots
under the workbook's declared cash, debt, revenue and profit definitions. Genuine
equivalents such as `INF`, `infinity`, `DEBT-FREE`, `TBD`, `awaiting data`, and
conditional calls are interpreted in their financial context by the evidence-bound
judge. A nonpositive-profit ratio may be unavailable when the denominator makes
the ratio economically non-meaningful; that does not authorize replacing a known
signed value with zero. Composite rules and disclosed vetoes are evaluated as the
candidate's actual policy rather than forced into one sentence or one-lower-bound
grammar. Numeric rounding follows the displayed precision; fabricated values and
unit changes without disclosure fail programmatic source settlement.

## Failure semantics

A missing, corrupt, or non-workbook deliverable is `INVALID_CANDIDATE` with strict
and lenient zero because the requested output is absent. Missing source packets,
judge credentials, exact replay records, LibreOffice calculation support, invalid
judge protocol, and transport failures are verifier infrastructure errors and
produce `UNMEASURED` with no numeric reward files.
