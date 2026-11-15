# Rubric

The machine source is `tests/scoring_params.json` with the executable predicates in `tests/validator.py`. The same parameters and rules apply to every artifact, model and condition. Deterministic predicates measure structure, source integrity, numeric limits and executable relationships. Semantic equivalence is measured by the request-bound `gpt-5.6-sol` source-bound judge in `tests/mix_judge/semantic_live.py`; keyword lists and punctuation do not establish a professional proposition.

## Strict Score

| Criterion | Weight | Subcapability Tags |
| --- | ---: | --- |
| bridge | 0.06 | domain-judgment, evidence-handling |
| multi_bridge | 0.03 | domain-judgment, evidence-handling |
| lights | 0.03 | domain-judgment, evidence-handling |
| movie | 0.06 | domain-judgment, evidence-handling |
| game | 0.03 | domain-judgment, evidence-handling |
| music | 0.03 | domain-judgment, evidence-handling |
| fixed | 0.06 | domain-judgment, evidence-handling |
| voice | 0.06 | domain-judgment, evidence-handling |
| latency | 0.03 | domain-judgment, evidence-handling |
| manual | 0.03 | domain-judgment, evidence-handling |
| smoothness | 0.03 | domain-judgment, evidence-handling |
| concurrent | 0.06 | domain-judgment, evidence-handling |
| network_loss | 0.06 | domain-judgment, evidence-handling |
| recovery | 0.06 | domain-judgment, evidence-handling |
| lamp_loss | 0.06 | domain-judgment, evidence-handling |
| priority | 0.03 | domain-judgment, evidence-handling |
| weak_network | 0.04 | domain-judgment, evidence-handling |
| upgrade | 0.03 | domain-judgment, evidence-handling |
| day | 0.03 | domain-judgment, evidence-handling |
| night | 0.06 | domain-judgment, evidence-handling |
| stability | 0.06 | domain-judgment, evidence-handling |
| environment | 0.03 | domain-judgment, evidence-handling |
| priority_rationale | 0.03 | domain-judgment, evidence-handling |

Strict reward is `max(0, sum(weight * measured completion) - sum(independent business damage))`. Item locations, prerequisite/action/expected-relationship checks and source-scope decisions are recorded in the verifier detail. All 23 existing criteria remain active.

The weights follow operational test risk rather than document length. Connection,
mode behavior, interruption/recovery, concurrent control, lamp loss, night behavior,
and stability receive the larger `0.06` shares because failure in any of those areas
can invalidate a release decision or leave the linked system in an unsafe or
unrecoverable state. Narrow variants and supporting controls receive `0.03` or
`0.04` because they refine coverage without replacing those primary workflows.
Together, environment and priority rationale retain enough credit to reward a
reproducible plan and an explainable execution order, while substantive product
behavior remains dominant. These values express relative QA responsibility; they
are not a score target or a uniquely exact allocation.

| Independent damage class | Penalty |
| --- | ---: |
| fabricated_execution | 0.03 |
| contradicted_behavior | 0.04 |
| unsupported_timing | 0.03 |

## Lenient Score

The binary score is the conjunction of parsed test cases, equipment/environment checklist, priority explanation and absence of fabricated execution or unsupported timing adoption. `Must-Have`, `Must Have`, and equivalent punctuation are the same MoSCoW label. The individual verdicts are stored in `lenient_must_have`; strict weights do not change this policy.

Repeated presentations of the same business case retain their content credit even when execution-status assertions differ. Fabricated status assertions remain independently chargeable. Distinct business cases sharing a copied body retain the existing template detection rule.

## Delivery Gates

HY Skill mean < 0.50; HY No Skill mean < 0.35; SOTA Skill mean < 0.50; each Skill-minus-No-Skill gap >= 0.15; SOTA Skill mean > HY Skill mean. Golden must score 1 and NOP 0. Effective trajectories and process judgments are validated separately.


## Critical Business Failure Discount (2026-10-18)

An actual execution-result cell asserts pass/passed/fail/failed although the task only requests an unexecuted test plan.

The existing positive and ordinary deduction calculations are retained. After
that settlement, multiply strict reward by **0.1** when this condition is evidenced,
once per artifact. Otherwise the factor is 1.0. A triggered critical defect also
fails the corresponding binary must-have. This is a multiplicative deduction,
with its evidence and before/after amounts recorded in critical_failure_discount.
It is applied uniformly to all submissions and does not depend on model or Skill
condition. Source: instruction.md: Leave execution results blank or explicitly unexecuted; do not invent execution results.
