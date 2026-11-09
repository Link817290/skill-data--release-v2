# Scoring rules

The final `/workspace/regime_map.xlsx` is scored condition-blind. Model identity
and skill installation are not inputs. Both standards use frozen
source facts, deterministic mathematical verification and required LLM semantic review. The
reference is one source-verified calibration, not the only acceptable answer.

## Continuous standard

```
weighted_row = 0.30 * joint_label_action
             + 0.30 * transition_support
             + 0.30 * evidence_alignment
             + 0.10 * flag_joint
row_credit = min(weighted_row, joint_label_action, transition_support)
strict = sum(row_credit) / 100
```

Each dimension is reported as a diagnostic mean over all 100 required samples.
The final reward averages the bounded row credit above. Correct evidence IDs or
flags cannot compensate for an unsupported final regime/action or failure to
apply the professional temporal rules on that row. This is a local decision-chain
bound, not a whole-workbook multiplier or score exponent. The judge assigns 1 for
supported completion, 0.5 for substantive partial completion and 0 for missing or
unsupported work, citing actual candidate fields and same-sample source facts.
Missing samples receive zero. Scores retain complementary credit within a valid decision chain rather
than applying arbitrary global coverage, F1, REVIEW-count or consistency cutoffs.

The three 0.30 owners carry equal weight because the delivered map needs all three
substantive parts at the same operating level: a usable final portfolio decision, a
chronologically supported state transition and a source-traceable evidence change set.
None is merely presentation, and overweighting one would let an otherwise unusable
decision chain pass by compensating with a different deliverable component. The flag
pair is 0.10 because it records two important review controls without replacing the
primary decision or its evidence. Together these weights represent the relative
business roles of the four owners. The row-level minimum then
enforces the dependency that evidence and flags cannot raise a row above its adopted
decision or temporal support.

Missing, wrong and unresolved are distinct observations. A missing required sample or
field receives zero on the owner that cannot be established. A supported but incomplete
business result may receive 0.5; an unsupported or contradictory result receives zero.
An unknown professional expression is preserved for semantic adjudication rather than
treated as either correct or wrong by a word list. One root cause is charged once per
business consequence: for example, an unsupported final regime can independently make
the regime/action pair and the chronological transition fail, but repeated wording of
that same error does not create additional damage. Evidence selection and flags remain
separate only when their actual source or control obligations are independently wrong.

- `joint_label_action`: the final regime and portfolio action are justified together.
- `transition_support`: persistence/switching is justified in chronological context,
  including inertia and loss of support. Correct non-switches count too.
- `evidence_alignment`: the complete appeared/disappeared anchor set is supported by
  current/previous source windows under a consistent calibration; sample events match.
- `flag_joint`: both current cluster contradiction and final review state are correct.

Conceptual professional rules remain binding under every calibration: the raw-regime
decision order, action override order, two-window state memory and turnover restrictions.
The judge receives these rules explicitly. An action is not correct merely because it
is described as cautious. In particular, MIXED permits rotation or HOLD, never a change
in gross exposure; NOISE permits HOLD or REDUCE_RISK; REVIEW requires REVIEW_ONLY,
and REVIEW_ONLY requires REVIEW. SIGNAL may HOLD after the turnover rule is applied.
For recognized equivalent enum values, these impossible adopted pairs deterministically
receive zero joint-label/action credit and fail material completion coherence. Other
professional equivalents remain subject to the same rules through semantic review.
An earlier incorrect candidate action is not automatically the normative state for
all later decisions; the judge evaluates the supported chronological chain.

Trend confirmation uses the original net-vote rule: the three member votes sum to
at least +2 or at most -2. A split such as `[+1,-1,+1]` remains neutral; the members
are not counted as independent cross-cluster confirmations.

For actually disclosed compatible cut lines, the program applies the raw decision
order and inertia to the source-recomputed cluster states for the whole panel.
Submitted previous labels never initialize or reset that state. A regime excluded
by this mathematical trajectory receives zero temporal credit. The trajectory does
not upgrade a semantic rejection or partial credit: mathematical consistency does
not endorse method reasonableness. All batches receive the same source-recomputed
trajectory when available. Other coherent methods, including those without a complete
numeric disclosure, continue through the required source-bound professional judgment;
no additional method-trace format is required.

Within a panel, semantic batches follow the original source chronology. Each batch
receives the preceding batch's source-evidence adjudications so a rejected submitted
state does not become the next batch's starting truth. These judgments remain evidence
to check against the source, not instructions or a new reference answer. Independent
workbooks can be evaluated concurrently.

For the source-recomputed disclosed calibration, evidence sets and flags are objective
mathematical checks. An exact appeared/disappeared set receives full evidence credit;
an inexact set cannot receive more than half, with its grounded partial value still
assessed semantically. Current cluster contradiction is computed from source votes;
the review flag follows the actual adopted final regime. Each correct flag contributes
half of flag credit. Unresolved enum meaning remains semantic. These checks do not
endorse a calibration: unsupported final decisions or temporal reasoning still bound
the row's final credit.

An alternative panel-relative calibration can earn full marks in all four dimensions.
Different thresholds, anchors, labels, actions or turn locations are not errors by
themselves. The judge uses the raw panel, dictionary, events, complete candidate panel
and the reference's source-derived states to distinguish supported alternatives from
invented or contradictory conclusions. Rationale is required and supplies context;
prose style is not a scoring dimension. There is no keyword-based narrative score.

### Sufficient positive source proof

The evaluator can certify a fully correct panel without asking the LLM to repeat
its arithmetic. It reads and hash-verifies the original issued CSVs and recomputes
one global calibration. Actually disclosed compatible cuts take precedence; an
invalid disclosed vector cannot fall back to the example calibration. Without a
complete numeric disclosure, the existing source-relative example can supply an
existence witness, not an assertion that the candidate disclosed those cuts.

This path requires all 100 samples and all five business fields to match the same
source-recomputed model. Evidence order is immaterial. Any unknown enum wording
must also be independently accepted as an unambiguous professional equivalent.
An additional required LLM judgment checks compatibility of the actual adopted
method and authenticity of the actual source claims, including rationale. Generic
rationale is valid; a genuinely contradictory method or fabricated source assertion
is not. Only the complete mathematical proof plus semantic admission certifies
all four dimensions. The receipt retains source hashes, cuts, every actual/expected
field and the bound semantic decision. It never reads the Golden artifact or actor
identity to determine eligibility.

Failure to establish this sufficient proof is not a deduction. The original
source-bound semantic path evaluates the panel, including other valid calibrations,
partially correct results and unknown professional expressions. No per-row mixture
of competing model answers is used. The strict aggregation and professional rules
are the same on both paths. The completion standard remains separately evaluated.

The evaluator can extract explicitly disclosed numeric cut lines from ordinary prose
or structured notation using the LLM. When a complete compatible vector is available,
it verifies numeric boundaries against the frozen source and deterministically
recomputes the candidate's anchor/cluster/inertia/action states with those cuts.
Compatibility requires every cut to lie within the observed range of its corresponding
frozen source field (absolute style magnitude for the style cut), and each declared
low/high pair for trend return, recent return, breadth, earnings, valuation percentile,
equity risk premium and liquidity must preserve `low < high`. No fixed reference cut
value or required percentile is imposed or disclosed by this boundary check.
This supplies a mathematical witness, not copied Golden labels. The final LLM still
judges source support and method reasonableness; a range-valid vector alone is not a
correct answer. Incomplete disclosures and other coherent models continue through
unconstrained source-bound semantic review. No JSON format, specific keys, global
rationale placement or exhaustive per-window method trace is required.

## Completion standard

`lenient = 1` when the explicit output contract and independent whole-map completion
checks pass; otherwise `lenient = 0`. Unambiguous adopted values and basic decision
coherence are checked over every row by program when all regime/action cells have
canonical meanings. This check uses the same compatibility rules as the strict
scorer. Professional expressions outside the recognized aliases retain LLM review
of their adoption and coherence. Substantive map delivery and usable source evidence
always receive an additional evidence-bound judgment. It does not read strict scores or AND all 400 per-row
quality verdicts. Local correctable quality errors do not automatically invalidate
the whole delivery. Empty or indiscriminate dumping, systematic fabrication and
material unresolved action contradictions fail, including an adopted MIXED with
ADD_RISK or REDUCE_RISK when that contradiction makes the delivered map materially
incoherent. A local incompatible pair still loses its strict row credit, but does not
by itself fail an otherwise complete and usable 100-row map; the evidence-bound
completion judgment decides materiality from the actual delivered panel. Thus lenient is not an exact-match
test or a numerical cutoff on strict. Per-row `meets_brief` remains diagnostic.

The two-window confirmation, persistence and turnover rules remain professional
requirements of the strict temporal-quality evaluation. Their standards are not
weakened or made optional by the separate, coarser completion lens.

The contract requires every sample exactly once, one legal regime/action, two Boolean
flags, at least one known anchor, all associated event IDs and a nonempty rationale
on every row. Unknown E_/EVT_ tokens remain visible and are errors. Known events must
belong to this sample, not merely occur elsewhere in the panel. Contract evidence
errors receive zero evidence credit on the affected sample; illegal enums receive
zero label/action and sequence credit; illegal flags receive zero flag credit.
Complete professional equivalents of enum values are adjudicated by the required
LLM, including expressions outside the documented notation aliases. Unrecognized
text is preserved for that review. A negation, unknown code or list of alternatives
does not adopt one legal value and earns no label/action or sequence credit.

No reference REVIEW overlap, REVIEW ceiling, macro-F1 floor or arbitrary global
consistency threshold determines success. All-REVIEW and other unsupported dumping
fail by the source-bound semantic obligations, rather than a hidden frequency rule.
The same supported alternative must be accepted under both standards.

## Method clarifications

Voting deduplication never deletes an anchor from the workbook: enumerate the complete
anchor sets first, then report their symmetric difference. The first window uses its
full set; identical adjacent sets fall back to the current full set. Append all and
only the sample's associated events. Disappeared anchors legitimately need not hold
in the current window, and change IDs alone do not establish current contradiction.

During an unconfirmed switch, prior MIXED/REVIEW retains the earlier unresolved
conflict/uncertainty until two matching raw readings confirm resolution. This can
legitimately differ from the current raw reading. Prior NOISE requires current event
intensity; prior SIGNAL requires two directional clusters. Derive actions from final
regime/current evidence, then apply turnover constraints. Flags describe current
cluster conflict and final review state independently.

## Runtime and reproducibility

`source_facts.json` is an evaluator-owned snapshot generated from original CSVs by
`task/tests/build_source_facts.py`. It includes source hashes and complete reference states.
The original source files and Golden workbook are preserved. Source facts are never
read from a candidate-modifiable workspace during grading.

Configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, and optionally
`LLM_JUDGE_MODEL` (default `gpt-5.6-sol`) and `LLM_JUDGE_CACHE_DIR` outside the
repository. The Responses API judge is mandatory, including for the Golden; no local
wordlist or reference-match fallback awards semantic credit. Cache keys bind the model,
prompt, criteria, source and whole candidate panel. API/schema failures are explicit
infrastructure failures, not fabricated task zeros: the result is semantically
`UNMEASURED`, the runtime writes `status=UNMEASURED`, exits nonzero and
does not publish reward files. Every returned criterion is checked
for complete coverage, valid credit, source/candidate citations and explanation.

`reward.txt` mirrors strict. `reward_strict.txt` and `reward_lenient.txt` retain the two
formal outputs. The authored reference is validated through the same current entrypoint,
and its trusted replay remains bound to the exact artifact, evidence and requests.
