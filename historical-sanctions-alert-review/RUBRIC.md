# Scoring methodology

## 1. Scoring summary

The task measures whether an agent can adjudicate historical sanctions alerts
and a related AML lookback without collapsing identity, legal status, transaction
scope, and suspicion into a single current-list result.

`reward_strict` is the weighted capability score. `reward_lenient` is an
independent completion score over the same deliverable. `reward` is a
compatibility alias for `reward_strict`.

| Capability dimension | Weight |
| --- | ---: |
| Entity resolution | 0.05 |
| Historical state reconstruction | 0.30 |
| Action and uncertainty discipline | 0.25 |
| AML pattern assessment | 0.05 |
| Cross-case control reconciliation | 0.30 |
| Evidence binding | 0.05 |

The two 0.30 dimensions are the central historical-review responsibilities:
reconstructing the operative state case by case and reconciling dependencies across
the queue. An error in either can reverse several blocking or escalation decisions.
Action and uncertainty discipline receives 0.25 because it converts that legal state
into operational handling, while depending on the identity and state analysis rather
than replacing them. Entity resolution, AML pattern assessment, and evidence binding
receive 0.05 each in this task because the issued queue already identifies the cases
and provides bounded AML groups and source records; these dimensions remain necessary
controls, but they have less decision breadth than temporal state, action, and
cross-case reconciliation. The weights describe review responsibility and affected
decision scope, not model performance or a target score.

The strict formula is the weighted sum of the six dimension scores, multiplied
by the source-integrity factor. The first four dimensions are means of their
case-level signals. The cross-case dimension is the mean of seven control
findings; a finding earns credit only when its conclusion, affected records,
material limitation, and defined fact request form a complete dependency chain.

The lenient formula is a binary conjunction of full case coverage, core
identity/state/action correctness, a substantive
decision for every alert, AML group and control finding, a case-local evidence reference
for each, a substantive summary, and unchanged source integrity. This lens does not compare the
calibrated legal or AML conclusions used by the strict lens.

Oracle/golden strict = `1.0000`; oracle/golden lenient = `1.0000`. The eight open
Directive 1 historical-state equivalents and the two wording-sensitive controls use the
required source-bound semantic judge. Closed categorical checks, structure, record
membership, dates, identifiers, citations, source hashes and aggregation remain
deterministic. The judge cannot replace missing identity, date, ownership, instrument or
tenor evidence with inference. Service, replay-cache-miss or verdict-validation failures
publish no score. Neither lens defines a passing score.

## 2. Deliverable profiles

With-skill profile: alerts distinguish true identity from legal effect, rebuild
the as-of state rather than projecting current records backward, date ownership
chains, preserve transaction-scope gaps for non-blocking restrictions, avoid
double counting summaries, and make AML referrals proportionate to evidence.

No-skill profile: a competent ad hoc review resolves obvious names and produces
complete-looking case notes, but tends to call every current true match blocked,
project a later ownership percentage backward, force a decision across a date
range, sum overlapping activity, or infer structuring from threshold-looking
amounts.

The scored differences are substantive outcomes. File names, JSON key names,
object order, capitalization, and wording are common to both profiles and do not
create credit.

## 3. Capability dimensions

### Entity resolution

Capability: resolve the legal party behind a screening candidate using name,
entity type, geography, identifiers, aliases, and corporate relations rather
than token similarity.

Professional reason: false positives and missed affiliates lead to opposite
operational errors even when the name-matching score is identical.

Anchor type: identifier, relation, and expert judgment record. The verifier
accepts equivalent match or false-positive language within each case object and
checks the outcome against the supplied transaction and list records. Object
order and field naming may change.

Attention role: must attend to party type and geography; must connect aliases or
ownership where relevant; must ignore shared generic words. Common failure:
treating a common bank or country word as identity evidence.

Skill section: `Stage 1: resolve the party, not the string`. This dimension
degrades without the skill when current list names are treated as conclusions
instead of hypotheses.

### Historical state reconstruction

Capability: apply the operative legal state to the transaction period,
including later designations, earlier sectoral measures, majority-owned
subsidiaries, and records spanning an effective date.

Professional reason: present-day list status does not answer whether an old
payment was blocked; the controlling state may be narrower, inherited, later,
or temporally indeterminate.

Anchor type: source location, enum status, temporal relation, and ownership
relation. The verifier checks whether each case expresses the supported state,
not a fixed sentence or heading.

Attention role: must connect transaction dates to dated actions and corporate
ownership; must ignore legal states that arose only later. Common failure:
backdating a current blocking designation or overlooking a contemporaneous
non-blocking restriction.

Skill sections: `Stage 2: rebuild the as-of state`, `Stage 3: distinguish
restriction types`, and `Stage 4: propagate ownership carefully`. Without the
method, the review typically follows the list snapshot's current labels.

### Action and uncertainty discipline

Capability: map the historical legal state to an operational action while
withholding a final prohibition decision when the record lacks a necessary
transaction date, product, issuance, maturity, tenor, or payment-term fact.

Professional reason: blocking a sectoral case is not conservative; it is the
wrong action. Clearing a payment as out of scope merely because a summary omits
product facts is equally unsupported.

Anchor type: relation and expert judgment record. The verifier requires the
action to cohere with identity and historical status and, for open cases, to
name decision-relevant evidence. Equivalent requests and professional wording
are accepted.

Attention role: must connect restriction scope to transaction attributes and
must attend to absent facts. Common failure: forcing a binary legal conclusion
from a bank-level transaction summary.

Skill section: `Stage 5: map legal state to action`. The no-skill profile closes
gaps as negatives or defaults to blocking; the with-skill profile makes a
bounded fact request.

### AML pattern assessment

Capability: reconstruct case-level activity at its actual grain, identify
supported patterns, avoid duplicate aggregation, and separate an investigative
lead from proof of illicit purpose.

Professional reason: summary rows can overlap, bank paths need not share a
customer, and familiar-looking amounts do not establish threshold evasion.

Anchor type: source record, temporal relation, invariant, and expert judgment
record. Each case is scored through several independent semantic signals: the
disposition, the observed pattern, the material limitation, and the defined
next inquiry. Synonyms and reordered reasoning are accepted.

Attention role: must connect related records within a case; must ignore prior
alert status as proof; must attend to missing customer, currency, purpose, and
row-grain evidence. Common failure: calling a bank-level pattern laundering or
structuring without the necessary linkage.

Skill sections: `Stage 1: understand the record grain` through `Stage 7:
maintain negative findings`. Without the skill, correct escalation labels are
often paired with unsupported narratives or double-counted totals.

### Cross-case control reconciliation

Capability: reconcile conclusions that depend on more than one alert or AML
group, including ownership chronology, an aggregate that crosses an effective
date, the complete post-effective non-blocking population, overlapping row
grain, reciprocal-flow limitations, different outcomes for superficially
similar threshold patterns, and AML independence from sanctions screening.

Professional reason: a queue can contain individually plausible notes that are
collectively inconsistent. A quality-control conclusion is usable only when it
identifies the affected records, preserves the decisive uncertainty, and asks
for the evidence that would actually resolve it.

Anchor type: relation, set membership, temporal comparison, and expert judgment
record. Each control is scored by dependency closure across the conclusion,
affected identifiers, material limitation, and fact request. Synonyms, field
names, prose order, and JSON collection names do not matter.

Attention role: must connect multiple rows without merging their legal or AML
states. Common failures include projecting a later ownership statement into an
earlier period, treating a range as a value date, or giving two similarly named
AML patterns the same unsupported conclusion.

Skill sections: the evidence ledger and dependency map in both supplied skills,
together with the historical-state, ownership, record-grain, overlap,
reciprocal-flow, and threshold-support stages.

### Evidence binding

Capability: make each disposition auditable through a resolvable record,
document, table, page, heading, FAQ, or list identifier.

Professional reason: later reviewers must be able to reconstruct both the fact
and the legal source without relying on the author's memory.

Anchor type: source location and identifier. The verifier checks for a
case-local source reference, not a prescribed citation format. This is the only
primarily mechanical dimension and represents five percent of the strict score.

Attention role: must connect each claim to its source. Common failure: a global
bibliography with no case-level binding.

Skill sections: `Build an evidence ledger before deciding` and `Stage 6: write
evidence-bound rationale`.

## 4. Anchor policy

Transaction identifiers and filing identifiers anchor record selection. Dated
actions and interpretive documents anchor legal status and scope. Corporate
reporting anchors historical ownership. List records anchor the candidate's
identity and current metadata. Transaction direction, date range, count, and
amount anchor AML observations. The financial-crime guidance and written expert
judgment embodied in the case expectations anchor evidentiary restraint.

Gold prose, sentence order, field order, and exact section names are not
anchors. A differently worded or reorganized deliverable receives the same
score when it preserves identifiers, decisions, relations, evidence limits, and
next actions.

## 5. Failure modes

- F1: a missing product, tenor, component date, currency, or customer link is
  treated as a negative fact instead of an open field.
- F2: a later ownership percentage is used as proof of an earlier ownership
  state without a transaction-time ownership record.
- F3: a current list result is accepted without checking dated actions and
  transaction records.
- F4: identity, status, action, or evidence from one alert is attached to
  another transaction.
- F5: a present-day blocked label is not overturned when the historical record
  establishes a different state.
- F6: the review fails to state the absence of the fact needed for a final
  sectoral or AML conclusion.
- F8: the conclusion is given without the record-to-rule reasoning needed to
  review it.
- F9: alert-level notes are individually plausible but the cross-case control
  population, limitations, or follow-up requests are inconsistent.

An unreadable deliverable scores zero. Modification or removal of supplied
source material applies the documented source-integrity factor. These are gates,
not score thresholds.

## 6. Robustness and anti-gaming

The verifier recursively locates case objects by stable transaction, filing, or
control identifiers. It does not depend on top-level collection names, JSON key
order, capitalization, or the reference answer's prose. For the ten accepted open
semantic criteria, professional synonyms, negation, attribution and uncertainty are
assessed against the source bundle and candidate spans rather than a phrase list.

Empty templates, source dumps, identifier-only files, and generic keyword blobs
cannot satisfy the linked identity, time-state, action, and case-specific AML
signals. Current-list copying cannot earn the historical-state or action
dimensions. Unsupported numeric totals do not earn AML credit.

## 7. Known limits

The supplied transaction data is institution-level and may summarize multiple
payments. The score therefore measures disposition and evidentiary discipline,
not a definitive finding about an underlying customer. Legal conclusions are
limited to the supplied sanctions materials and the stated U.S. correspondent
bank context.


## 8. Semantic Control Equivalence

`EFFECTIVE-DATE-RANGE` requires the complete professional dependency: the two-payment
aggregate crosses 29 July 2014; the range cannot date either component; the review asks
for both individual payment records and accurate execution, settlement or value dates;
and it asks for the financing facts needed to assess a post-effective component. These
meanings may be distributed across fields and use any accurate professional wording.

`OVERLAP-CONTROL` requires recognition that the relevant aggregate periods overlap,
that raw sums cannot be treated as unique activity or are unreliable before
deduplication, and that underlying membership plus stable payment identifiers or
equivalent deduplication keys are needed before unique counts or values are calculated.

The semantic judge must quote candidate spans and is supplied with the source facts for
these controls. It does not use a phrase list or accept co-occurring terms without the
dependency. The deterministic evaluator independently checks the affected record set and
case-local sources. Golden transaction 227538 uses its actual 9 April 2015 through
22 April 2016 period; the ownership gap concerns the effective date and continuity of
the reported 97.52 percent interest across those component dates, not a fictitious 2014
transaction period.
