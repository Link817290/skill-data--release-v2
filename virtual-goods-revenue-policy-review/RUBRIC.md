# Scoring rubric

Deliverable: `/workspace/revenue_policy_review.csv`. The same condition-blind deterministic scorer evaluates both runtime conditions and reports two co-equal standards. It does not inspect a trajectory, model identity, or skill availability.

```text
evidence_state_i = conclusion_factor_i *
                   (0.55 * relation_closure_i
                  + 0.15 * source_binding_i
                  + 0.10 * residual_evidence_i
                  + 0.20 * audit_response_i)

reward_strict  = integrity_gate * sum((1 / 30) * evidence_state_i)
reward_lenient = 1 if usable_traceable_issue_ledger
                    and count(evidence_state_i >= 0.50) >= 12 else 0
reward         = reward_strict
```

The conclusion, source-binding, residual-evidence, and audit-response components are adjudicated by the source-bound `gpt-5.6-sol` judge. The conclusion component is `1.0` for an equivalent evidence state, `0.5` for a materially qualified partial state, and `0.0` for a reversed, invented, or unsupported state. A conclusion that correctly separates an adopted disclosure from still-open underlying audit evidence receives the supported state for the policy and preserves the gap in its residual-evidence field. The judge accepts professional equivalent expressions, negation, attribution, and ordinary section locators; filenames, supplied-source hashes, and CSV shape remain deterministic checks. Strict measures calibrated professional judgment across all thirty findings. Lenient combines the ledger delivery contract with a quality floor: at least twelve independently matched findings must each reach an evidence-state score of `0.50`. Because that floor reuses strict issue evidence, the two lenses are not independent.

Golden strict = `1.0000`. Golden lenient = `1.0000`. The semantic judge is required for answer scoring; a service failure aborts scoring rather than returning a guessed zero. No arbitrary pass threshold is defined.

## Deliverable profiles

**With-method profile:** The ledger reconstructs each question-to-final-disclosure chain, overturns earlier positions where the issued record does so, separates accounting propositions that reach different evidence states, preserves material unresolved absences, and proposes assertion-specific closing work.

**Competent ad hoc profile:** The ledger accurately summarizes several prominent disclosures and may identify the restatement, but tends to treat management's detailed response as support, merge separate presentation relationships, carry an earlier recognition pattern into the final position, or infer that an omitted matter was resolved.

The strict dimensions below score those substantive differences. Column labels, row order, finding identifiers, prose style, and notation are not skill-attributable and carry no strict weight.

## Capability dimensions

### Evidence-state judgment across contradictory versions

Weight: `30 x (1/30 x 0.55)` within strict, plus the conclusion multiplier applied to the full issue score.

- **Capability:** Determine whether each accounting position is supported, superseded, modified, or unresolved as of the final reporting record.
- **Professional reason:** A response letter, draft filing, and issued filing can each state a complete but incompatible conclusion. Audit review must not confuse an assertion with adoption or evidence.
- **Anchor type:** relation; enum_status; expert_judgment_record.
- **Verifier signal:** One-to-one semantic issue matching followed by evidence-state classification and coverage of the decisive cross-version relationship.
- **Attention role:** must_connect the staff question, management response, interim disclosure, final policy, and control consequence; must_ignore rhetorical confidence and obsolete policy wording.
- **Accepted variation:** Equivalent status labels and any professional phrasing that preserves the evidence state and relationship. Rows and sections may appear in any order.
- **Common failure:** Treating every management response as supported, or treating the newest sentence as sufficient without identifying what it displaced.

### Source binding and version traceability

Weight: `30 x (1/30 x 0.15)`.

- **Capability:** Bind each material conclusion to the files and stable document locations that support both sides of the version chain.
- **Professional reason:** A reviewer must be able to reperform the conclusion without rediscovering the record, and a change conclusion normally needs both the earlier and final positions.
- **Anchor type:** source_location; relation.
- **Verifier signal:** Coverage of the independently expected source files plus a comment, note, page, heading, or equivalent locator in the row's evidence field.
- **Attention role:** must_attend to primary record locations; must_connect sources across time.
- **Accepted variation:** Full or shortened file names, natural document descriptions, and different stable locators are accepted.
- **Common failure:** A bare source name, a citation only to the staff question, or a citation only to the final prose for a supersession conclusion.

### Residual-evidence discipline

Weight: `30 x (1/30 x 0.10)`.

- **Capability:** State the evidence still needed to close an assertion and explicitly preserve a genuinely indeterminate matter.
- **Professional reason:** Audit review cannot convert missing contracts, population reconciliations, model support, or materiality analysis into positive assurance.
- **Anchor type:** expert_judgment_record; relation; invariant.
- **Verifier signal:** A substantive evidence need whose concepts align with the issue; an explicit no-further-evidence statement is accepted only where the expert record permits it.
- **Attention role:** must_attend to what the supplied record does not contain; must_ignore the urge to complete every conclusion positively.
- **Accepted variation:** Any specific evidence request that addresses the same assertion and population.
- **Common failure:** Blank evidence fields, generic requests to “obtain support,” or a fabricated resolution of the absent bundle analysis.

### Assertion-specific audit response

Weight: `30 x (1/30 x 0.20)`.

- **Capability:** Design work that can close the identified risk rather than merely restating the accounting rule.
- **Professional reason:** A review note is operational only when the proposed procedure identifies the evidence, population, and assertion it will test.
- **Anchor type:** expert_judgment_record; relation; invariant.
- **Verifier signal:** Presence of an executable audit action and semantic alignment with the expert response for that issue.
- **Attention role:** must_connect the accounting effect to source systems, contracts, estimates, transactions, and controls.
- **Accepted variation:** Alternative procedures that test the same assertion are accepted; exact verbs and sequencing are not required.
- **Common failure:** Recommending only additional discussion, repeating a standard, or proposing one generic procedure for every row.

## Anchor policy

Every expected issue originates in a question, position, revision, omission, estimate change, audit report, or control statement in the supplied primary documents. The expert ledger was produced first by a reference solution that reads those materials and aborts if a cited passage or the scored disclosure absence changes. Hidden ground truth is then derived from that finished ledger.

The scorer does not compare sentences with the golden prose. It canonicalizes professional synonyms into concepts, matches issues by their accounting relationships, accepts status synonyms, and checks source locations independently. Gold wording, row numbers, headings, punctuation, and finding IDs are not anchors.

The Docker image copies only `task/environment/workspace/` into `/workspace`. That directory contains the six primary records, the blank CSV template, and the integrity manifest. Runtime methods, including `SKILL.md`, its two referenced method documents, and its generic text-extraction utility, remain under `task/environment/skills/` and are mounted separately by the harness; those method files are not workspace materials or source records and are absent from the materialized no-skill task.

## Lenient standard

`usable_traceable_issue_ledger` is true when all of the following hold:

- the CSV is readable and resolves the eight requested fields, including accepted header aliases or a positional equivalent;
- it contains at least six substantive issue rows, with no row-count upper limit;
- the ledger uses at least two meaningful evidence states;
- its citations collectively resolve to at least three supplied source records;
- every substantive row addresses residual evidence;
- it is not a raw-source dump; and
- supplied source files remain unchanged when they are present beside the deliverable.

The ledger must also contain at least twelve independently matched issue judgments whose
relation, evidence, residual-evidence, action, and conclusion score is at least `0.50`.
This is a quality floor over the strict issue ledger, not a second weighted total.

Lenient scoring does not require complete agreement across all thirty expert conclusions,
but its twelve-issue quality floor uses the same expert-anchored evidence states as strict.

## Gates

| Gate | Condition | Strict effect |
| --- | --- | ---: |
| readable | no parseable finding rows | x0 |
| ledger conformance | requested fields do not resolve | x0.6 |
| source integrity | any supplied source or blank template changes | x0.5 |
| source dumping | overlong source transcriptions or embedded source markup | x0.4 |
| repeated shell | more than forty percent of rows repeat the same substantive text | x0.2 |

## Failure modes measured

- **F1, withholding an unsupported conclusion:** the subscription-bundle treatment is not established by the final policy record.
- **F3, going back to verify:** dense position statements must be checked against two later filing versions.
- **F5, overturning supplied text:** detailed management positions are later identified as erroneous or revised.
- **F6, confirming absence:** a commercial product description appears in the final document while the relevant accounting analysis is absent from its policy section.
- **F8, separating reasoning from conclusion:** a status alone earns little unless the row closes the cross-source reasoning and proposes issue-specific work.
- **F10, bundling distinct judgments:** one paragraph can contain policy, allocation, materiality, and remediation assertions that require different evidence states.
- **F7, multi-step state tracking:** implementation, management assessment, external control assurance, and a later estimate change occur at different reporting dates and cannot be collapsed into one current-state label.

## Robustness and anti-gaming

The regression probes cover reordered rows, renamed columns, synonymous conclusions, empty delivery, all-favorable and all-adverse shells, numeric and keyword stuffing, source dumping, repeated shells, and source tampering. One candidate row can satisfy only one expert issue, preventing a single dense paragraph from claiming the full issue set. The scoring concepts are accounting relations rather than exact golden sentences.

Known limit: the semantic judge still depends on evaluator availability and source-derived expert anchors. Deterministic checks remain limited to file shape, source integrity, and delivery gates; professional paraphrases are evaluated in context rather than by a fixed vocabulary.

2026-10-24: There is no 40-row upper limit or row-count dump penalty. Duplicate shells, verbatim source markup and extreme per-row transcription remain checked on their actual content. Legitimate additional independent findings are neutral. One-to-one assignment is constrained by an evidence-bound semantic locator of each independent directional accounting proposition; topic/conclusion, subject, polarity and conditions must match. Shared generic concepts cannot connect adjacent but different propositions. Unavailable judge aborts scoring rather than returning a candidate zero.
