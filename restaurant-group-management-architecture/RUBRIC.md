# Scoring Rubric

The primary score is continuous and has no hard score cap:

```text
reward_strict = positive_earned * retention
positive_earned = sum(item weight * item completion)
retention = product of coefficients for distinct adopted damage instances
```

Repeated wording of one underlying error is charged once. Omission loses the corresponding positive credit; it does not also create a deduction unless the candidate adopts a harmful contrary proposition.

## Evaluation Layers

The program layer parses the declared Markdown deliverable, decision roles, explicit structural relationships and task violations. Open semantic equivalence is evaluated by a single condition-blind `gpt-5.6-sol` Responses request against the issued material and `group-control-design` references. Every nonzero semantic result must cite exact candidate and source units. The judge preserves subject, object, relation, polarity, modality, conditions, exceptions and adoption status; word lists and co-occurrence do not establish a business proposition.

Golden has one request-bound replay. An unseen request requires a live model call. A judge failure publishes no reward rather than a candidate score of zero.

## Positive Credit

| Item | Weight | Professional purpose |
| --- | ---: | --- |
| P03 | 0.09 | Unit competitive-strategy authority follows the BU that directly manages the unit. This tests usable unit accountability rather than copying the organization chart. |
| P04 | 0.05 | Pension development and competition decisions identify the Group as both drafter where applicable and final decider. Explicit final accountability is required. |
| P07 | 0.20 | Key incubation business remains listed-company-direct; its development and competition strategies both identify the listed company as final decider. The larger weight protects a central settled boundary. |
| P11 | 0.13 | Investment BU positioning and duties: 35% virtual/on-behalf positioning, 20% capital-operation substance, 25% target supervision and correction, 20% professional investment review without final approval. Equivalent professional duties are accepted semantically. |
| P12 | 0.31 | N+1 architecture: 20% three-level structure, 30% condition-specific destinations for every Group-direct object, 15% mature new BUs, 15% entity status, 20% function ownership. The largest weight reflects the amount of conditional architecture work required. |
| P13 | 0.17 | Dual-sector architecture: 10% actual sectors, 10% listed/capital platforms, 15% park BU, 15% pension BU, 20% level/BU-nature consistency, 30% receiving platform functions. |
| P14 | 0.05 | Target and budget chain: equal shares for Group aggregates/boundary, listed-company BU/incubation targets, board issuance to each diversified business, Investment-BU preparation/implementation/correction, and Hotel-BU issuance to hotels. The specific material overrides the general cascade default. |

P04 and P07 require the explicit final decision body; drafting language alone is incomplete. P11-P14 are evaluated by the unified source-bound semantic judge.

## Deductions

| Item | Coefficient | Adopted damage |
| --- | ---: | --- |
| D01 | 0.20 | Strategy authority is affirmatively assigned to a materially wrong level. |
| D02 | 0.80 | Source-bound review finds hotels or key incubation businesses actually placed under Investment-BU direct scope. Parallel listed-company-direct objects are preserved. |
| D03 | 0.80 | The Group bypasses the listed company to issue operating targets to transferred units. Aggregate targets and valid Group-direct exceptions are excluded. |
| D04 | 0.20 | The dual-sector variant contradicts its level or BU-nature logic. |
| D05 | 0.80 | N+1 contradicts its three-level/entity-BU logic. |
| D06 | 0.20 | A settled headquarters control type is affirmatively reversed. |
| D07 | 0.80 | Near-term Investment BU is made an entity, headquarters or department-owning unit. |
| D08 | 0.80 | Hotel BU or Investment BU receives unsupported final investment/asset approval. |
| D10 | 0.80 | Source-bound review finds an unsupported fact tuple: subject, metric, value, unit and time/scope do not match the XX restaurant materials. Comparison-case numbers cannot support this Group. Supported calculations and marked unknown thresholds are allowed. |
| D11 | 0.20 | A required substantive unit is absent: either long-term variant, headquarters-function placement, target responsibility, or decision allocation. |
| D12 | 0.30 | An undeclared regular deliverable is added beside the required file. |
| D13 | 0.30 | A substantive section is written in a language other than Chinese. |

Character counts are diagnostic only. They are not a deduction item and never affect either score lens.

## Lenient Lens

`reward_lenient` is binary. It requires the general continuous threshold and damage ceiling plus complete P04 and P07 responsibility chains and at least 75% completion for P11, P12, P13 and P14. This balances near-term authority, target responsibility and both long-term variants; document length does not affect the gate.

## Excluded Golden Units

Seventeen Golden units have no independent positive weight because they are contextual enumeration, non-propositions, optional unsettled choices, blank authority cells or presentation detail. `task/tests/rubric-contract.json:not_scored_golden_units.unit_rationales` gives the reason and remaining positive or deduction coverage for every unit. Their correctness is not silently ignored.
