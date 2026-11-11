# Cooperative D2D relaying manuscript revision rubric

Scorer version: 2.2.0. Deliverable: `output/revised_manuscript.pdf`.

The verifier extracts the PDF by columns with pinned PyMuPDF 1.28.2, renders every candidate page and the
archived source figures, and obtains a required source-bound semantic judgment.
Missing service, invalid evidence or an unresolved judge response is an
infrastructure error and produces no score. The judge sees the issued source,
candidate text, rendered evidence and every criterion; exact candidate spans
bind positive evidence. Model identity and skill condition are unavailable to
the scoring predicates.

## Strict calculation

`strict = max(0, sum(weight * completion) - sum(triggered deduction values))`.
This is a bounded-additive settlement with a zero floor. It is the exact
`strict_formula` declared by `task/tests/scoring_params.json` and
`dataset.toml`; deductions are fixed professional-severity values, not
multiplicative retention factors.

The ten positive owner weights sum to 1.00. Semantic owners receive a fraction
in [0,1] supported by source-bound evidence; native delivery checks are binary.
Partial semantic credit distinguishes a valid but incomplete argument from a
missing or wrong one. Missing content receives zero completion. Present but
wrong content receives zero for that owner and may also trigger a deduction only
when it affirmatively damages a separate protected responsibility. This avoids
double-counting ordinary omissions while charging adopted contradictions,
fabrication and source corruption.

The numerical values are a public, coarse-grained severity policy rather than
unique scientific constants. Positive weights use five bands: 0.05 for local
native delivery, 0.08 for supporting framing/proof/preservation scope, 0.10 for
material domain/consistency scope, 0.12 for major model/proof/algorithm links,
and 0.15 for the central support theorem. Deduction values use the same meaning:
0.08 local evidence loss, 0.10 material integrity harm, 0.12 major model
corruption, and 0.15 replacement of the objective, algorithm or publication
identity. Values are based on professional consequence, dependency position and
remaining manuscript value. They do not depend on a particular implementation
style or surface wording, and no claim is made that these are the only
defensible nearby values.

| Owner | Weight | What is measured |
|---|---:|---|
| framing | 0.08 | Cooperative D2D relaying research question in title and abstract |
| support_bound | 0.15 | Valid optimum representation with at most U active patterns |
| sparsity_bound | 0.12 | Sparse nonnegative coefficients preserving optimal effective rates |
| caratheodory_dimension | 0.12 | Correct ambient/affine dimension and support consequence |
| simplex_dimension | 0.08 | Supporting-face/simplex reduction to at most U points |
| candidate_budget | 0.12 | U budget propagated through candidate update, compression and re-optimization |
| positive_rate_domain | 0.10 | Strictly positive effective-rate domain for the sum-log problem |
| stale_bound_cleared | 0.10 | No currently adopted contradictory 2U claim |
| preserved_core | 0.08 | Mean preservation of six original model/algorithm/evidence subowners |
| delivery_integrity | 0.05 | Mean of five native readability/completeness checks |

### Positive owner basis

**framing — 0.08, semantic fraction.** It assesses whether the title and
abstract frame the issued cooperative D2D relaying/time-reuse question rather
than a replacement HetNet paper. Framing guides the reader but does not prove
the corrected bound, so it is lower than each mathematical/algorithm owner.
It depends on the issued research object, not on the proof chain. A missing
title/abstract framing earns zero; a partially accurate framing can earn partial
credit; a replacement question earns zero and may reduce preserved content.

**support_bound — 0.15, semantic fraction.** It assesses an actual argument that
an optimum can be represented with at most U active patterns, not a theorem
heading or copied inequality. This is the earliest and highest-consequence
technical correction, so it carries the largest positive weight. It depends on
the relaxed effective-rate representation and supports the sparsity, dimension
and algorithm-budget owners. A missing proof earns zero; an incomplete but
valid line of reasoning can earn partial credit; a mathematically invalid U
claim earns zero and can also cause internal-consistency harm if adopted
downstream.

**sparsity_bound — 0.12, semantic fraction.** It assesses nonnegative normalized
coefficients, preservation of the optimal effective-rate vector and the derived
`||x*||_0 <= U` consequence. It is a major downstream theorem responsibility,
weighted below the existence proof but level with the dimension and algorithm
propagation owners. It depends on support_bound. Omission earns zero; a bare
inequality without the construction earns zero; a correct but locally incomplete
derivation may receive partial credit.

**caratheodory_dimension — 0.12, semantic fraction.** It assesses the dimension
in which Caratheodory is applied and why the conclusion is U points rather than
U+1. This step closes the central mathematical gap and is weighted with the
sparsity and candidate-budget responsibilities. It depends on the effective-rate
space introduced by support_bound and precedes simplex_dimension. Missing
dimension reasoning earns zero; a correct U-dimensional invocation that stops
at U+1 is incomplete/incorrect for this owner; an equivalent supporting-face
proof is accepted.

**simplex_dimension — 0.08, semantic fraction.** It assesses the proper-face or
simplex reduction that turns the ambient result into at most U support points.
It is necessary proof closure but narrower than the main support/dimension
owners, hence 0.08. It depends on caratheodory_dimension and Pareto optimality.
Missing face reduction earns zero; a stated dimension with no strict reduction
earns zero; a concise valid equivalent argument receives full credit.

**candidate_budget — 0.12, semantic fraction.** It assesses whether the theorem
actually controls the iterative candidate set, temporary expansion, support
compression/pruning, re-optimization and advancement with `|V| <= U`. An
unpropagated theorem does not repair an executable algorithm, so this owner is
weighted with sparsity and dimension. It depends on the corrected support chain
and the original algorithm state. Missing algorithm propagation earns zero; an
isolated U token earns zero; a partly closed but valid state transition can earn
partial credit. Replacing the original algorithm can also trigger a deduction.

**positive_rate_domain — 0.10, semantic fraction.** It assesses the strictly
positive effective user rates required by the sum-log objective, without
incorrectly requiring all links/intermediate rates to be positive. This is a
feasibility/domain condition for the proof and objective, but narrower than the
support chain, hence 0.10. It depends on the preserved effective-rate definition
and objective. Missing the domain earns zero; the wrong domain earns zero; a
correct equivalent statement earns full credit.

**stale_bound_cleared — 0.10, semantic fraction.** It assesses all currently
adopted theorem, algorithm and conclusion claims for consistency with U.
Text explicitly rejecting or comparing the superseded 2U statement is allowed
and counts are diagnostic only. It depends on the completed correction chain. A
missing cleanup or an adopted U/2U contradiction loses credit; rejected context
does not.
Material adopted contradictions also trigger their independent deduction.

**preserved_core — 0.08, mean of six semantic subowners.** It averages decision
variables, time-reuse profile, sum-log objective, Hamming-neighborhood mechanism,
Frank-Wolfe/update mechanism and actual archived figure evidence. These issued
units constrain revision scope and prevent a new paper/algorithm from scoring,
but each is auxiliary to the requested proof repair, so their combined owner is
0.08. The first three are model prerequisites; the latter three preserve the
algorithm/evidence chain. Missing and wrong subowners both contribute zero to
their mean; affirmative removal of objective, both algorithms, variables or
figures can additionally trigger the matching damage owner.

**delivery_integrity — 0.05, mean of five native checks.** It averages readable
text, at least one readable page, abstract, references and algorithm presence.
The task requires a complete conference paper but publishes no fixed page floor;
semantic manuscript_completeness supplies the substantive completeness check.
This small weight rewards native usability without allowing formatting to
outweigh mathematics. A missing check contributes zero to the mean. A materially
truncated manuscript additionally triggers its damage owner and fails lenient.

The five correction-chain owners support_bound, sparsity_bound,
caratheodory_dimension, simplex_dimension and candidate_budget total 0.59. This
majority reflects the requested theorem-to-algorithm repair. Weighting is based
on scientific consequence, dependency position and revision scope.

## Damage owners

| Damage owner | Deduction | Trigger and rationale |
|---|---:|---|
| replaced_objective | 0.15 | Sum-log PF objective affirmatively removed/replaced; the research problem changes |
| replaced_algorithm | 0.15 | Both Hamming and Frank-Wolfe mechanisms removed; the issued algorithm is replaced |
| dropped_figure_evidence | 0.08 | Archived topology/allocation/CDF evidence affirmatively absent |
| dropped_decision_variables | 0.12 | Issued x/y/z roles removed or replaced |
| fabricated_evidence_claim | 0.10 | Claims unsupported newly run experiments/measurements/runtime evidence |
| capacity_constraint_corruption | 0.12 | Replaces the original discrete capacity inequality or conflates it with the downstream full-use relaxation |
| authorship_or_affiliation_corruption | 0.15 | Removes, replaces, guesses or invents author/affiliation identities |
| citation_corruption | 0.10 | Removes/replaces required citations or invents sources |
| material_internal_contradiction | 0.10 | Currently adopted proof/model/algorithm/conclusion claims materially conflict |
| truncated_manuscript | 0.10 | Manuscript is materially incomplete rather than a conference paper |

Deductions charge affirmative damage beyond ordinary missing positive content;
they are additive before the zero floor and never a fixed total-score cap. The
0.15 objective/algorithm/authorship amounts reflect replacement of the research
object, executable method or publication identity. The 0.12 variable/capacity
amounts match major model corruption. The 0.10 fabrication, citation,
contradiction and truncation amounts are material scientific-integrity failures.
Figure loss is 0.08 because it removes issued evidence without by itself changing
the formal model. Missing and wrong values trigger the same owner when both make
that responsibility unusable; the evidence record distinguishes omission from
an affirmative false claim. One finding maps to one damage owner, avoiding
repeated regex-like penalties for the same defect.

Root-cause de-duplication is explicit. A discrete/relaxed capacity-layer error is
owned by capacity_constraint_corruption and is not charged again merely because
it also makes the proof inconsistent. The original single-server formulation
must retain its inequality and idling allowance. The downstream multi-server
relaxation may use the requested pattern-aware full-use equality when the
manuscript keeps the layers distinct and justifies why the relaxed problem
remains an upper bound. Missing authorship is owned by
authorship_or_affiliation_corruption and is not charged again as generic
truncation. An independent U/2U adopted contradiction or missing abstract can
still trigger material_internal_contradiction or truncated_manuscript. Thus a
missing item loses its positive owner (and a required lenient gate) while a
present but affirmatively wrong item also receives exactly the separate damage
owner justified by its root cause.

Fabrication is judged semantically over the whole manuscript. “We did not rerun
the simulation” is compliant; a quiet but affirmative new-experiment claim fails.
The private source contract contains both artifacts supplied by the task owner:
the issued May draft and the later authoritative reference manuscript. Citations,
figures and numerical evidence already present in either supplied source are
archived evidence. A candidate may not introduce an unsupported third evidence
set, and matching the reference does not excuse a source/model contradiction.
Capacity corruption is an independent 0.12 damage and a lenient hard failure, so
the skill's central warning against lifting a relaxation property into the
original feasible set cannot collapse into a preserved_core mean of a few
thousandths.

## Lenient score

Lenient is a binary minimum-usable-manuscript contract, not a threshold on
strict and not “nine components >= 0.5.” It equals 1 only when:

- the PDF is readable and contains an abstract, references and an algorithm;
- framing, all five proof/correction owners, positive_rate_domain and
  stale_bound_cleared each equal 1;
- decision variables and the sum-log objective equal 1;
- at least one original algorithmic mechanism equals 1; and
- authorship, citations, original capacity meaning, experimental integrity,
  internal consistency and manuscript completeness each equal 1.

Thus a locally partial but scientifically promising proof keeps strict partial
credit but does not pass the complete-paper lens. Conversely, a truthful denial
of new experiments does not fail. Missing authors, affiliations, abstract,
references or algorithm; invented authors/citations/evidence; a U/2U adopted
contradiction; or an inequality-to-equality model corruption all fail lenient.
The exact owner vocabularies, weights, aggregations, deduction values and lenient
IDs are machine-owned by `task/tests/scoring_params.json`; validator startup
rejects a version, vocabulary or weight-sum mismatch.

The stable lenient component IDs are `framing`, `support_bound`,
`sparsity_bound`, `caratheodory_dimension`, `simplex_dimension`,
`candidate_budget`, `positive_rate_domain`, and `stale_bound_cleared`. The
stable integrity IDs are `authorship_integrity`, `citation_integrity`,
`capacity_constraint_integrity`, `experimental_integrity`,
`internal_consistency`, and `manuscript_completeness`. The scorer validates
these vocabularies against the parameter file before assigning a reward.

## Semantic and visual evidence

Equivalent proofs, notation and concise explanations are accepted. Bare
equations and keywords without their mathematical argument do not earn proof
credit. Text is extracted independently by column. Candidate pages and archived
source figures are rendered independently, so a CDF label or blank frame is
insufficient. Graphics must preserve actual original evidence or faithful
redrawings; no new simulations may be invented.

Configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_MODEL` and `LLM_JUDGE_API_KEY`;
optional `LLM_JUDGE_REASONING_EFFORT` and evaluator-owned
`LLM_JUDGE_CACHE_DIR` support fresh and exact request-bound replay. Credentials,
endpoints and ordinary-candidate replies are not
packaged. The private tests include one Golden-only replay whose binding combines
request, artifact and evidence hashes and whose manifest seals request metadata,
the response decision, validated review and validation receipt. Its provenance
is a fresh OpenAI Responses `gpt-5.6-sol` adjudication; encrypted reasoning
payloads are not packaged.
Fresh semantic calls use OpenAI Responses `/v1/responses`, default
`gpt-5.6-sol`, and reasoning effort `high`. A transport, schema or evidence
failure is `UNMEASURED`; no alternate protocol or semantic fallback can emit a
business score.
Every non-Golden binding miss proceeds to evaluator-owned replay/fresh; cache
misses, unavailable service or malformed evidence are infrastructure errors with
no silent keyword fallback. Actor images contain only the environment context
and cannot read the private Golden replay.
