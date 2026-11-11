# Scoring Rubric

Deliverable: `/workspace/network_design_recommendation.xlsx`.

A deterministic verifier scores every submission from three inputs: the submitted workbook, the frozen source workbook `Supply chain logisitcs problem.xlsx`, and relations recomputed from that source. It does not read the trajectory, compare free text with a gold narrative, or require the reference workbook's sheet names, column order, or layout. Scoring evaluates the network-design decisions and the evidence behind them, not wording or presentation.

## Score Form

```text
strict = positive_earned * retention
         positive_earned = sum over the eight positive items of (weight * completion)
         retention       = product over damage instances of the smallest
                           coefficient among the deduction items in that instance

lenient = 1.0 when every must-do item holds, else 0.0
          must-do items: D01, D03, D12, D13, D14 raise no damage instance;
                         P01, P02, P04, P06, P07 and P08 satisfy their
                         explicit business invariants. P03 and P05 remain
                         continuous strict owners.

reward = strict
```

Weights and coefficients are read from `tests/scoring_params.json`. Each dimension's completion is a continuous 0-to-1 measure of that capability. Lenient is a second lens over the same settled ledger: it asks whether the indispensable business invariants are present, while presentation and optimization quality remain continuous strict owners. It does not read the weighted total or apply an arbitrary composite-score threshold.

For strict settlement, one root defect may name several deduction items; that damage instance uses the smallest coefficient among those items once, then independent damage instances multiply. This avoids charging one network-design defect repeatedly while allowing unrelated professional failures to compound according to their separate operational harm. The coefficients preserve the independently reviewable value that remains after each severity class.

**Eligibility assessment.** Assignment eligibility is assessed locally in P01. There is no squared global multiplier on P01–P08; other dimensions retain their independently computed service/capacity checks.

## Scoring Dimensions

Each dimension is one positive item. Weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| --- | --- | --- | --- | --- | --- |
| P01 | Current constraint semantics | Share of claimed primary assignments current eligibility supports; route validity against a current `AIR` rate row whose path, service, and weight band close; capacity integrity of claimed facility flow; route evidence recorded per assignment | `ProductsPerPlant`, `VmiCustomers`, `PlantPorts`, `FreightRates`, `WhCosts`, `WhCapacities`, and independently recomputed order-to-facility eligibility | 0.07 | Constraint reasoning |
| P02 | Exception boundary | Share of the order population carrying an explicit decision; accuracy of the cause class recorded against each claimed exception, judged against recomputed eligibility, taking the weakest register where more than one table classifies the same exceptions; coverage of the exceptions the source relations make structural; and conservation between the exceptions the workbook states and the orders its own plan leaves unserved | Recomputed order-to-facility eligibility, `WhCapacities`, the submitted primary and exception registers | 0.06 | Constraint reasoning |
| P03 | Lexicographic operating footprint | Facility register coverage of all 19 facilities; use / not-used status against positive valid flow; capacity and assigned-count reconciliation; absence of an unsupported permanent-closure claim; compactness, at full credit only when the plan reaches maximum service (2,410 orders) with the minimum facility count (12) | `WhCapacities`, valid primary flow, source-derived maximum service and minimum footprint | 0.14 | Optimization judgment |
| P04 | Primary allocation economics | The independently verified service/cost basis (65% service effectiveness, 35% cost efficiency) multiplied by the share of assignments whose displayed warehouse, freight and total costs reconcile. This dependency reflects the task's decision-ready, auditable workbook requirement: a hidden independent recomputation cannot rescue false displayed economics | `WhCosts`, `FreightRates`, order quantities and weights, submitted cost fields, recomputed reference variable cost | 0.30 | Quantitative modeling |
| P05 | Workbook lineage | Density of live formulas in the primary allocation detail, of cross-sheet formulas in that detail, and of formulas outside it, so detail-scale and summary-scale calculations stay linked | OOXML formula cells and their cross-sheet references | 0.10 | File handling |
| P06 | Single-facility outage screening | Whether the outage register covers every facility the submitted plan uses; per outage, maximum recoverable service, minimum variable cost at that service, and the split between orders with no remaining current path and orders with a remaining path but no capacity; the governing outage named consistently in the register and the summary, and marked on the row the register itself ranks lowest | Source-derived per-facility outage results, submitted positive-flow facility set | 0.16 | Scenario analysis |
| P07 | Governing-outage recovery | Order-level recovery closure for the governing outage: population addressed, assignment validity against remaining eligibility, capacity-feasible recovered service against the source-derived maximum, cause classes for unrecovered orders, route evidence, recovery variable cost, exclusion of the unavailable facility, and facility reconciliation | Remaining eligibility graph with the unavailable facility at zero capacity, source capacities, current tariff rows | 0.12 | Multi-step reasoning |
| P08 | Feasible primary service | Independently eligible and capacity-feasible served count divided by maximum service; the selected order IDs may differ from the reference optimum | Source eligibility, capacities and maximum service | 0.05 | Constraint reasoning |

The weight distribution follows the brief's decision responsibilities and the professional harm caused when each responsibility fails. P01-P03 and P08 jointly carry 0.32 for legal service, exception closure and the minimum operating footprint. P04 carries 0.30 because variable cost is the third lexicographic decision objective and the workbook must expose correct handling, freight and total amounts for leadership review; false displayed costs make the economic recommendation unusable even when the verifier can independently reconstruct the hidden optimum. P05 carries 0.10 for the live lineage needed to audit those amounts. P06-P07 jointly carry 0.28 because every used-facility outage and the governing recovery plan are explicit resilience deliverables. These owners add continuously, preserving partial value for independently correct work without imposing a fixed total-score cap.

### Owner Semantics And Dependencies

`tests/scoring_params.json#owner_basis` stores the same contract and `validator.py` rejects missing, extra or incomplete owner-basis entries before settlement.

| Owner | Professional importance and relative weight | Prerequisites | Why this calculation | Missing versus wrong |
| --- | --- | --- | --- | --- |
| P01 | Feasibility owner (`0.07`): illegal edges or capacity make the plan infeasible; kept below P04 and combined resilience to avoid charging the same service objective repeatedly | Primary decisions; relationship, route and capacity records | Continuous weighted mean preserves credit for independently completed eligibility, route, capacity and evidence components | Missing route evidence keeps limited partial route credit; an unsupported assignment explicitly fails eligibility |
| P02 | Constraint-boundary owner (`0.06`): hidden or misclassified unserved demand changes the reason for network failure | Primary register; recomputed eligibility; explicit unserved population | Coverage, cause accuracy, structural coverage and conservation are complementary outcomes | Missing rows reduce coverage/conservation; a stated wrong cause reduces accuracy rather than becoming unknown |
| P03 | Requested footprint decision (`0.14`): facility use and reconciliation must support the minimum full-service footprint | Valid primary flow; capacities; derived minimum facility count | Additive register components allow local repair; compactness is full only at maximum service and minimum footprint | Missing components lose their component; contradictory status/count loses reconciliation and may trigger separate damage |
| P04 | Core economic decision (`0.30`): false displayed costs make leadership review unusable | Feasible primary allocation; source costs/tariffs; submitted cost fields | `(0.65 service + 0.35 independent cost efficiency) × correct cost coverage` keeps the optimization basis dependent on auditable disclosure | Missing and wrong costs both fail audit coverage; hidden verifier recomputation cannot rescue wrong displayed economics |
| P05 | Auditability support (`0.10`): live lineage lets reviewers reproduce and repair calculations | Recognised detail table; formulas with actual cell/range dependencies | Separate detail, cross-sheet and summary density ratios measure distinct lineage layers | Missing lineage scores zero for that layer; constant/zero-factor decoration is excluded as wrong evidence |
| P06 | Complete outage screen (`0.16`): every used facility is an explicit resilience case | Positive-flow facility set; derived outage results; comparison register | Event coverage plus per-event metrics and verdict consistency reflect breadth and correctness; wrong verdict retains only `0.35` | Missing events reduce coverage; wrong stated metrics reduce accuracy; silence is not converted to a false assertion |
| P07 | Executable governing recovery (`0.12`): summary-only analysis cannot operate continuity actions | Correct governing event; failed site removed; recovery population/eligibility | Continuous recovery components are bound to the selected event; detailing another event retains only `0.35` | Missing rows reduce population closure; invalid assignments or failed-site flow are explicit errors |
| P08 | First objective check (`0.05`): maximum feasible service must be achieved | Valid assignments; derived maximum service | Direct feasible-served ratio accepts equivalent optimal populations and avoids reference-ID overfit | Missing service reduces the ratio; invalid claimed service is excluded rather than counted as missing |

### Partial credit and accepted variation

Every dimension is continuous; its components are scored separately and summed.

- **P01** — Equivalent facility assignments and tariff rows with equal applicable economics are accepted, as is any professional table or field vocabulary. An assignment to an eligible facility whose route evidence does not resolve keeps one quarter of its route credit. Common failure: reverse the customer restriction, replay the demand record's historical plant or carrier fields (`historical_replay`), or price a weight band that does not contain the shipment weight.
- **P02** — The exception register may be a separate sheet or a cause column on the primary register, in any professional vocabulary for the two cause classes. Where more than one table classifies the same exceptions, the weakest classification is taken: two tables that classify one exception differently cannot both be the answer. Common failure: describe an order with no eligible path as a capacity shortfall, leave the unserved orders implicit instead of stating them, or classify only a sample of them.
- **P03** — Any equally compact service-maximizing footprint is accepted; no unique facility list is required. Capacity and assigned-count reconciliation earn half credit each per facility row. A cached formula must equal the independently reconstructed flow; an uncached formula earns this credit only when its `COUNTIF` dependency binds the submitted allocation's facility column to the facility on that row. Formula presence alone is not reconciliation. Common failure: minimize variable cost before service, or report a permanent closure the supplied records cannot support.
- **P04** — Any exact or heuristic optimization technique and any cost-equivalent allocation are accepted. Common failure: drop orders to lower cost, apply shipment weight twice, or charge company freight to customer-arranged `CRF` service.
- **P05** — Sheet names, styles, tables, formula syntax, row order, and column order are unrestricted. A cell's cached result is read where the file supplies one, and an uncached formula counts only when it contains a cell or range dependency. Constant or decorative formulas disconnected from decision detail do not establish lineage. Common failure: rename a flat export as XLSX, or insert decorative formulas disconnected from decision detail.
- **P06** — Scenario names, comparison orientation, optimization package, and equal-cost recovery assignments may vary; an alternative valid primary footprint changes the required outage set automatically. A register of correct per-outage metrics that names the wrong governing facility, a register whose governing mark sits on a row it does not itself rank lowest (recoverable service ascending, then minimum variable cost descending; not judged when a row's service is an uncached formula), or a summary whose declared governing facility or recoverable-order count contradicts the register, retains 0.35 of the dimension. Common failure: screen all facilities instead of the used set, reuse primary assignments after capacity removal, or select the most expensive rather than the lowest-service event.
- **P07** — Any service-maximizing, cost-equivalent recovery allocation is accepted, in any professional long or separate-table structure; the event being detailed is read from the table that details it, not from every recovery row in the workbook. Recovery detail for an event other than the identified governing outage retains 0.35 of the dimension. Common failure: keep flow at the failed site, provide only facility totals, silently omit unrecovered orders, or minimize cost by serving fewer orders.
- **P08** — Any equal-objective feasible population is accepted, including different order IDs. Invalid edges and capacity overages do not count as feasible served orders. Reference ID precision/recall are diagnostic only.

## Deductions

Each damage instance multiplies the score by its coefficient.

| Item | Error | Damage instances | Coefficient | Rationale |
| --- | --- | --- | --- | --- |
| D01 | The supplied source workbook is modified; its hash differs from the frozen source | once | 0.1 | The brief requires the source to stay read-only, and a mutated source invalidates every figure derived from it |
| D02 | Duplicate or conflicting primary order decisions | once | 0.9 | One order cannot carry two decisions; the register stops being a decision record |
| D03 | Recorded method reversal, first | one instance per reversed rule; D03-D08 fill in order, at most six | 0.9 | A workbook that records the opposite of the rule it was asked to apply is not the auditable decision record the brief asks for |
| D04 | Recorded method reversal, second | as above | 0.9 | As above |
| D05 | Recorded method reversal, third | as above | 0.8 | As above |
| D06 | Recorded method reversal, fourth | as above | 0.8 | As above |
| D07 | Recorded method reversal, fifth | as above | 0.8 | As above |
| D08 | Recorded method reversal, sixth | as above | 0.9 | As above |
| D09 | The facility register's declared status contradicts the plan's own valid flow: a facility marked not used that still carries flow, or one marked in use that carries none. Only a literal status is compared; a status formula without a cached result is not | once | 0.5 | A register that disagrees with the allocation it summarises cannot be read as the decision record the brief asks for |
| D10 | A summary, notes or audit cell states that company or `AIR` freight is charged to customer-arranged `CRF` orders, and the statement carries no negation | once | 0.3 | The brief: "`CRF` remains customer-arranged with no company freight cost" |
| D11 | A summary, notes or audit cell affirmatively states that the analysis used, obtained or depended on the internet, a public tariff or other external data. Statements that the work is independent of external data or exclusively uses supplied/workspace material are compliant | once | 0.3 | The brief: "use only materials under `/workspace`, do not use the internet or rely on information not supplied there" |
| D12 | The primary order tables list fewer than 90% of the day's 9,215 orders by source order identifier | once | 0.5 | The brief requires the primary allocation and every primary exception; a partial-day register is not the requested decision record, though independently reviewable work retains half its strict value |
| D13 | The outage register covers fewer than 90% of the facilities the submitted primary plan uses (not charged when the plan uses none) | once | 0.5 | The brief requires every such single-facility outage; incomplete screening blocks operational completion while retaining half the value of independently correct analysis |
| D14 | `network_design_recommendation.xlsx` is missing and another workbook is scored in its place | once | 0.5 | The brief fixes the deliverable path; a reviewable substitute workbook retains half its strict value but cannot satisfy the declared delivery contract |

Six rules are checked, each stated in the task brief itself:

1. the governing outage is the one with the **lowest** recoverable service;
2. service ranks ahead of footprint and of variable cost in the objective order;
3. a structural exception is one with **no** eligible facility path, before capacity is considered;
4. the source workbook stays read-only;
5. capacity, routes, rates, and service are not invented for unsupported orders;
6. the facility-scoped customer restriction is directional and is not reversed.

Open prose meaning is owned by the required source-bound semantic judge, not by keyword or regular-expression credit. The program judge remains authoritative for numeric assignments, formulas, relations and conservation. An affirmative reversal, unsupported permission or external-source reliance fails the semantic owner even when all expected terms appear; compliant negation and equivalent professional wording pass. Judge failure is UNMEASURED.

### Interactions with the dimensions

- A systematic conclusion reversal discounts P01, P02, P03, P04, P05 and P08 by its rate. It is measured two ways and the larger rate applies: the share of the four independent places stating a governing verdict (the screening register's marks, the summary's declared facility, the summary's declared recoverable-order count, and the recovery detail's event) that land on the facility the inverted rule would select, counted only when at least two of those places state a verdict; and the two-sided swap rate of an exception register in which each cause class carries the other's label, counted only when each class has at least 20 rows. P06 and P07 are not discounted this way; they carry their own 0.35 residuals instead.
- Naming the wrong governing outage, or contradicting the register in the summary, retains 0.35 of P06. Detailing recovery for a different event, or detailing it under a screening verdict that is itself wrong, retains 0.35 of P07.
- P03 gives compactness full credit only when maximum service and the minimum positive-flow facility count are both achieved. Service effectiveness itself is measured in P04 and P08 rather than multiplied into P02/P03 a second time.

## Automatic Failure

There is no automatic failure for formatting alone. A missing deliverable, or a file that cannot be opened as a workbook, earns no dimension credit and scores 0; a workbook scored in place of the declared file carries D14. Every other penalty is a multiplicative deduction rather than a score cap.

## Lenient Lens

Lenient is binary and is settled from the strict ledger's own per-item results. It is 1.0 only when all of these hold:

- the supplied source is unchanged (D01 not raised) and no recorded method reversal is present (D03 not raised);
- the primary order tables list at least 90% of the day's orders (D12 not raised);
- the outage register covers at least 90% of the facilities the submitted plan uses (D13 not raised);
- the deliverable is `network_design_recommendation.xlsx` (D14 not raised); and
- P01 requires every claimed assignment to be eligible, route-valid and capacity-consistent;
- P02 requires complete population, structural-exception and conservation closure;
- P04 requires complete displayed-cost coverage for a nonempty feasible service plan;
- P06 requires screening every used facility, P07 requires feasible governing-outage recovery, and P08 requires maximum feasible service;
- P03 and P05 remain continuous strict owners for footprint quality and formula lineage.

The binary lens reads the same P01–P08 observations as strict; it adds no alternate semantics or fixed total-score cap. Equivalent optimal assignments and layouts remain accepted under the same per-item rules.

## Anchors and Robustness

Every scored assertion resolves to source locations, identifiers, numeric derivations, relation direction, enums, or network invariants. Reference wording, exact sheet names, column order, styles, and agent self-certification are not anchors: the reference workbook's `Order Allocation`, `Outage Screening`, and `Input Audit` sheets are one valid arrangement, not a required one. The verifier discovers tables through stable identifiers and semantic header families, resolves internal cross-sheet references, and checks values rather than a layout.

The following valid changes preserve both scores: renaming or reordering worksheets and columns, reordering records, professional synonym changes, formula-linked identifiers, and an alternative equal-objective assignment. Source mutation, duplicate or conflicting decisions, and unsupported claimed assignments affect the relevant gate or dimension.

## Failure Modes and Anti-Gaming

Empty delivery, keyword sheets, numeric shotgun, source dump, all-assigned, all-unassigned, `historical_replay`, primary-only analysis, and a scenario shell with no recovery decisions cannot satisfy the capability dimensions. Formula quantity alone cannot establish correctness, and a recovery plan for a non-governing event receives only limited credit because it does not answer the decision requested.

## Known Limits

The workbook supports a current-day operating footprint and deterministic single-facility recovery under the supplied capacity, relationship, and variable-cost records. It does not establish permanent closure, fixed opening economics, inventory policy, lease, tax, emissions, stochastic outage probability, greenfield construction, or multi-period investment. Recovery may use another current facility; that permission is not evidence for capital expansion.

Eligibility affects P01 locally. P08 measures source-eligible, capacity-feasible service relative to the maximum-service objective and accepts equally good solutions with different order IDs. Reference ID overlap is diagnostic only. Header resolution gives exact headers across the entire row priority over descriptive substring matches. Structural and capacity exception-count labels accept professional equivalents. Scalar summary declarations require a label/value row; an outage-register metric header does not declare a summary value.
