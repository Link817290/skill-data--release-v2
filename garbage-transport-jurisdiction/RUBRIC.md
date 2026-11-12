# Rubric

Subability tags: `case-support`, `forum-exclusivity`, `forum-choice`,
`evidence-request-content`, `evidence-channel`, `purpose-limitation`.

The verifier requires three editable Chinese Word deliverables. File presence
and parseability are deterministic. Strict reward assigns 75% to the thirteen
source-bound filing owners below and 25% to a semantic review of object/scope
binding, polarity/status, requirement coverage, and source fidelity. The filing
owners carry most of the weight because they represent distinct legal requests
and evidence obligations. No single factual anchor dominates that layer:
the jurisdiction relationship, origin, requested relief, forum non-exclusivity
and forum choice together carry 60%, while the two property-specific evidence
requests, their event records, lawful fallback channels and use limitations
together carry 40%. The semantic layer has material weight so equivalent
titles, dates, addresses, and legal expression are judged by meaning rather
than exact wording. There is no Golden-signature exception, center adjustment,
shared scale, or score cap.

## Positive criteria

| ID | Weight | Criterion |
| --- | ---: | --- |
| G_J_RELATION | 0.08 | The filing coherently connects the oral arrangement, own-vehicle transport, and per-trip freight obligation. |
| G_J_ORIGIN | 0.15 | The filing binds the documented Jiangnan origin to the transport-jurisdiction rule and selected court. |
| G_J_RELIEF | 0.07 | The filing requests both reconsideration of the rejection and acceptance of the filing. |
| G_J_FORUM_EXCLUSIVITY | 0.12 | The filing correctly treats the defendant-domicile forum as nonexclusive. |
| G_J_FORUM_CHOICE | 0.18 | The filing correctly applies the claimant's available forum choice. |
| G_F_CONTRACT | 0.05 | The Fengge Yulin request binds the relevant contract and payment-record categories to that property manager. |
| G_F_EVENTS | 0.06 | The Fengge Yulin request binds the dated vehicle ledger and corroborating records/witness source. |
| G_T_CONTRACT | 0.05 | The Tianguang He Huayuan request binds the relevant contract and payment-record categories to that property manager. |
| G_T_EVENTS | 0.06 | The Tianguang He Huayuan request binds the dated two-vehicle ledger and corroborating records/witness source. |
| G_F_CHANNEL | 0.04 | The Fengge Yulin request uses a lawful court-facing fallback channel. |
| G_T_CHANNEL | 0.04 | The Tianguang He Huayuan request uses a lawful court-facing fallback channel. |
| G_F_PURPOSE | 0.05 | The Fengge Yulin request jointly limits use and third-party disclosure. |
| G_T_PURPOSE | 0.05 | The Tianguang He Huayuan request jointly limits use and third-party disclosure. |

For each owner, full credit requires every registered prerequisite to be affirmatively adopted for the correct object, scope, polarity, conditions, and procedural status. A broken prerequisite chain earns zero for that owner. Independently completed owners retain their credit.

## Deductions

| ID | Coefficient | Harmful adopted assertion |
| --- | ---: | --- |
| D01 | 0.7 | States that only the defendant-domicile court may hear the dispute or that the Jiangnan District court cannot accept it. |
| D02 | 0.7 | States that the absence of a written contract prevents a transport contract or freight claim from existing. |
| D03 | 0.9 | Claims that a private request itself creates fines or detention, or invents an already issued judicial investigation order. |
| D04 | 0.1 | Upgrades an unverified project fact into an established fact, including converting entry/photo records into completed transport counts or inventing an exact residence. |
| D05 | 0.9 (inactive) | Retired compatibility identifier. Document length relative to Golden is not a business defect; unsupported or irrelevant content is assessed by its substantive owner. |

Negated, quoted, rejected, unknown, or explicitly unresolved statements do not trigger these deductions. Repeated manifestations of one causal error against the same business object are deduplicated. D01-D02 affect only the linked filing owners, D03 only the corresponding request channel, and D04 the factual owners in the affected document. D05 is retained as an inactive compatibility identifier. Local retention is bounded at 0.1, so a positive raw score is never compressed by more than 10x.

## Lenient score

The binary lenient score is `1` only when all three declared documents are
present, the program filing gate passes, and each of the four semantic
dimensions is at least 0.75. This requires a coherent filing, source-faithful
jurisdiction facts, lawful request channels, and correct object/scope binding in
both evidence letters.
