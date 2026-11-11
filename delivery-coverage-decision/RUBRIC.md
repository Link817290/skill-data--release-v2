# Evaluation rules

`task/rubric.json` defines the numerical and business criteria and their weights.
The active text review contract is `task/tests/mix_judge/contract.json`. Numerical
results are reconstructed from the public records; text review checks the
meaning, evidence, operational actions and limits of the submitted work.

The four semantic-review weights in `task/tests/mix_judge/contract.json` are a
diagnostic review vector. Final strict settlement uses the owner-chain weights
in `task/rubric.json`; the two vectors are intentionally separate and recorded
as such in the contract.

Accept source-supported equivalent calculations, wording and defensible choices.
Honor the filenames, fields and units disclosed in the instruction and public
interface. A conflicting reference must be investigated rather than used to
penalize a source-correct answer. A repeated consequence of one numerical error
is not a separate business error; an independently unsupported action can be.

The `business_failure_conditions` entries identify concrete errors covered by
the corresponding existing criteria. They do not add hidden deliverables or
require the reference's exact prose. Ordinary formatting carries no aesthetic score.

`tests/evaluate.py` first applies the shared Bench published-file gate declared
in `rubric.json`. A missing required file gives a genuine delivery-failure score
of zero. The first existing declared report format is the primary report; extra
root files are charged 0.02 each by the capped `DX_DELIVERABLE` rule.
Calculation support files inside their declared directory are permitted.

Strict reward is a weighted sum across independent business owners. Source
state, event lineage, spatial conversion, operational feasibility,
reconciliation, plan population and investment decision are each charged once;
one lineage defect does not multiply through otherwise measured owners. The
`订单状态` current-message field contains only IDs from the highest business
revision; the separate historical-message field preserves the full audit trail.
Conflicted branch attributes are checked field by field, so a local retained
attribute loses local continuous credit instead of zeroing the entire table.
Current lineage itself remains an independent owner.
semantic 18% follows its published 30/30/25/15 diagnostic proportions, yielding
5.4%, 5.4%, 4.5% and 2.7% of the final reward. There is no global exponent. An explicitly asserted wrong
plan is an independent 0.4 damage; all nonfatal damage retains at least half of
earned credit, while a missing required deliverable remains a fatal zero.
Known source-constraint violations are criterion failures; actual solver,
transport or judge-protocol failures remain unmeasured, never numeric-only mixed
credit. Header wrapping, a blank generic summary heading above the retained
public row labels, and explanatory notes after a blank table separator do not
erase otherwise readable business records. Wrong row metadata remains an error
but does not make an unchanged source-valid allocation infeasible.
An omitted unassigned ledger row remains a coverage failure. It does not invent
an operation: the offered assignment set can still be checked against all
source demand, capacities and objectives. Its expected unserved classification
for summary verification is derived from source eligibility, never inserted
into the actor artifact. Unsupported served records remain real failures.

The 82% program share reflects that feasibility, allocation, reconciliation,
and budget decisions are closed computations over the issued records. Within
that share, operational feasibility receives 23% because an infeasible route or
capacity plan cannot be executed; investment decision receives 15% and
reconciliation 12% because they support the final recommendation and its audit
trail. Source state and event lineage receive 10% each, spatial conversion 5%,
and plan population 7% as prerequisite evidence owners. The remaining 18% is
semantic because recommendation meaning, trade-offs, interpretation, and scope
cannot be reduced to one literal string. The split expresses relative business
responsibility rather than a uniquely exact statistical constant.

Semantic reference facts now come from the current reference workbook only
after independent verification against the original inputs. Legacy author-only
CSV reference tables with stale rounding are not represented as verified facts.
This numerical certificate does not certify every narrative claim in Golden.
Request-bound replay checks current evidence against the archived request.
Keep all runtime outputs outside the package.

## Lenient Lens

`reward_lenient` is a binary conjunction of the five must-have decisions in
`task/rubric.json`; it is not derived from the weighted strict total. It equals
1 only when:

1. the declared workbook, calculation entry point, calculation README and one
   selected report are all published;
2. the canonical order population has at most one isolated
   revision/state/event-lineage mismatch;
3. served assignments carry complete directed service times and substantiate a
   source-feasible lexicographic optimum;
4. resource-use rows and scenario summaries reconcile to the submitted
   assignment ledger; and
5. quoted terms, robust-plan metrics and the adopted recommendation agree under
   the documented priority order.

These conditions represent the minimum usable decision package: a readable
delivery, traceable source state, executable allocation, reconciled results and
a supported recommendation. Failure of any one makes lenient 0 while strict
retains continuous credit for independently correct owners. Evaluator or solver
infrastructure failure remains unmeasured and is never converted into lenient 0.


## Skill Process Subability Tags

Process review is separate from artifact reward and applies only to with-skill trajectories.

| Process criterion | subability_tag |
|---|---|
| Skill discovery | `skill-selection` |
| Source precedence and event lineage | `source-precedence-and-event-lineage` |
| Constrained network allocation | `constrained-network-allocation` |
| Scenario decision and claim boundaries | `scenario-decision-and-claim-boundaries` |
