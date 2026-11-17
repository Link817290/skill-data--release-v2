# Food Lot Containment Scoring Rubric

One model-blind scorer applies to every artifact. The seven source-grounded
criteria are measured before settlement. Strict reward combines three local
dependency chains and one independent owner; there is no global exponent.
Golden earns 1.0 and a missing published delivery earns 0.0.

| ID | Weight | Subability tag | Criterion |
| --- | ---: | --- | --- |
| P01 | local | `source-reconciliation` | Complete supported product, package, date and code scope. |
| P02 | local | `amendment-delta` | Identify only newly included package variants and the supported action date. |
| P03 | local | `relationship-preservation` | Preserve product-channel relationships and notice-level geography. |
| P04 | 0.13 | `operational-communication` | State the supported recipient actions without claiming completion. |
| P05 | local | `amendment-interpretation` | Explain that added packs supplement earlier scope and keep date meanings distinct. |
| P06 | local | `scope-boundary-reasoning` | Keep product identity, customer relationships, geography and physical quantities distinct. |
| P07 | local | `evidence-limits` | Preserve the historical cutoff, unresolved identifiers and closure limits. |

The identification/relationship chain is `0.46 * min(P01, P03)`. The amendment
chain is `0.07 * min(P02, P05)`. The bounded-distribution chain is
`0.34 * (P06 * P07)`. Independent recipient action contributes `0.13 * P04`.
These four contributions are added, preserving credit across independent owners.
If all four semantic owners P04-P07 are zero, the required notice is unusable
and strict reward is zero. The ledger also reports a same-weight arithmetic
owner-credit baseline for compression auditing; that diagnostic is not reward.

The identification/relationship owner receives 46% because a recall pack with
the wrong product or channel population cannot contain the affected stock. The
bounded-distribution owner receives 34% because unsupported shipment or closure
claims create a separate operational and legal risk. Recipient action receives
13% so a correct scope still loses material credit when recipients cannot act.
Amendment interpretation receives 7% because it is narrower but still prevents
the added packs from replacing or corrupting the earlier scope. These values
express relative containment responsibility, not a uniquely exact allocation.

Numerical items are reconstructed from the public records. Semantic items use
the source-bound contract in `task/tests/mix_judge/contract.json`; its internal
semantic subtotal remains diagnostic and does not replace the strict formula.
The program judge scores named product/customer relationships that can be
resolved deterministically. Additional rows whose product identity and notice
references are source-supported are passed to the semantic owner to distinguish
notice-level distribution scope from an asserted named-customer shipment; they
are never accepted or rejected by channel keywords.

Lenient reward requires complete product, amendment and named-relationship
registers together with an actionable notice, bounded distribution claims and
explicit historical/evidentiary limits. The published delivery gate separately
requires both `preparation/build_registers.py` and `preparation/README.md`.
Each verdict reuses the corresponding independently measured item; a fractional
strict result never silently becomes a lenient pass.

Accept source-supported equivalent calculations, wording and defensible choices.
Honor the filenames, fields and units disclosed in the instruction and public
interface. A conflicting reference must be investigated rather than used to
penalize a source-correct answer. A repeated consequence of one numerical error
is not a separate business error; an independently unsupported action can be.

The `business_failure_conditions` entries identify concrete errors covered by
the corresponding existing criteria. They do not add hidden deliverables or
require the reference's exact prose. Ordinary formatting carries no aesthetic score.

`tests/evaluate.py` combines complete numerical and semantic measurements.
Missing or invalid required service results withhold measurement; they do not
silently receive numerical-only credit. Request-bound replay checks the current
evidence against the archived request. Keep all runtime outputs outside the package.
