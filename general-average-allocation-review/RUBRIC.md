# Scoring Rubric

This rubric scores the two deliverables — the technical memorandum
`general_average_review.md` and the reconciliation schedule
`general_average_schedule.csv` — against the supplied general-average adjustment and
the three judgments in the decision record. Scoring reads the substance of the
review: the adjustment arithmetic, the basis and treatment of each contributing
interest, the classification of allowances, the liability and collection position,
and the evidential limits the record supports. Wording, heading names, section order
and table layout are not scored.

## Score Form

```text
strict = positive_earned * retention
         positive_earned = sum over the seventeen positive items of (weight * completion)
         retention       = product over damage instances of the smallest
                           coefficient among the deduction items in that instance
```

Weights and coefficients are read from `tests/scoring_params.json`; the 17 item
weights sum to 1. Each item settles a fixed set of scored checkpoints, and its
completion is the share of its own checkpoints the deliverables earn: a
one-checkpoint item is a single 0/1 decision and a multi-checkpoint item is its hit
rate over the checkpoints it covers. A lenient 0/1 usability lens is reported next to
the strict score (see below).

The weights reflect professional consequence and audit effort. The contributing-
interest basis receives 0.08 because an error there propagates through every
allocation. The principal arithmetic, allocation routing and evidence-sensitive
travel split receive 0.07 each because they are independently reconcilable controls
that materially change the fund. The account-action and authority controls receive
0.05 or 0.06 where they constrain collection without changing the arithmetic by
themselves. These are relative importance weights, not hidden pass thresholds; each
multi-part item still gives proportional credit for the professional findings it
actually establishes.

## Scoring Dimensions

The 17 positive items settle 34 distinct checkpoints, each belonging to exactly one
item. In the Evidence column, `adjustment` is `general_average_adjustment.pdf`,
`first instance` is `first_instance_judgment.pdf`, `court of appeal` is
`court_of_appeal_judgment.pdf` and `final judgment` is `final_judgment.pdf`; an
`F`-number is the corresponding determination in the reference memorandum's finding
register.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| --- | --- | --- | --- | --- | --- |
| P02 | Unchallenged factual platform | The intermediate appeal proceeded on the trial factual findings, which were not challenged; two owner grounds had permission and a late third was abandoned | F48; court of appeal paras.3, 29-30 | 0.06 | Authority reconciliation |
| P03 | Scope of the payment-evidence statement | The adjusters' statement that payment evidence was seen concerns the disbursement accounts examined, not proof that every cargo contribution was paid | F33; adjustment p.11 | 0.07 | Settlement boundary |
| P07 | Instrument-level reconciliation before release | Each cash deposit, bond and guarantee requires account-by-account reconciliation to its governing instrument before any refund, release or demand | F61; adjustment pp.9-10, final judgment paras.20-21, 146 | 0.06 | Settlement boundary |
| P12 | A6a Marseille travel split | Gross USD 15,035.72 divides into USD 5,011.91 remainder and USD 10,023.81 general average | F73; adjustment pp.63-64 | 0.07 | Timing and substitution |
| P15 | Burden allocation remained operative | Cargo had to establish causative unseaworthiness and the owners then had to establish due diligence; the proposed reversal was rejected at trial | F42; first instance paras.55-57, court of appeal paras.12, 31 | 0.05 | Authority reconciliation |
| P18 | Bonds and guarantees: no instrument register | Standard Average Bonds and Guarantees incorporated a Non-Separation Agreement, but no account-level instrument register or terms supporting a blanket release or demand are supplied | F36; adjustment p.10 | 0.05 | Settlement boundary |
| P23 | Electronic-chart carriage in 2011 | The absence of official electronic charts was not unseaworthiness in 2011 because no such carriage requirement then applied and coverage was limited | F44; first instance paras.118-120 | 0.05 | Authority reconciliation |
| P24 | Paid and resisting cargo populations | Most cargo interests had paid while about 8% resisted, and the 8% deposit call and the approximately 8% resisting population are different measures that cannot be substituted for one another or for the aggregate cargo contribution | F17, F35; final judgment paras.19-20, adjustment pp.10, 95 | 0.05 | Settlement boundary |
| P38 | No account-level order in the dismissal | Dismissal of the owners' appeal resolves the litigated recovery claim, but the judgment contains no account-level monetary, refund or security-release order for other interests | F40; final judgment paras.20-21, 146 | 0.05 | Settlement boundary |
| P39 | Salvage security lodged for cargo | Vessel interests lodged salvage security on behalf of cargo so the laden voyage could continue; that fact does not prove cargo paid its later general-average contribution | F62; adjustment pp.7, 9 | 0.07 | Settlement boundary |
| P41 | Rule routing of the allowance classes | Salvage to Rule VI, lightening and reshipping to Rule VIII, refuge and detention during bunker reloading to Rule XI, and other direct-consequence expenditure to Rule C or, for YAR 1994, Rule XI(d) | F65; adjustment p.9 | 0.07 | Timing and substitution |
| P52 | Deposit call versus final rate | The 8% cash-deposit call was provisional security and must not be used as the final debt or rate; the final blended adjustment rate is 2.67460000% | F18; adjustment pp.9, 95 | 0.05 | Settlement boundary |
| P62 | Further classification and burden treatments | Pollution expenditure routed differently by contract population; Voucher B9 excluded despite its position in the China sequence; the D10 sub-trips; the divergent A6 subitems; section C wholly admitted across the detention period; and payment kept separate from loss classification (6 checkpoints) | F67, F71, F72, F74, F76, F77; adjustment pp.11, 50-51, 65-66, 71-72, 75-78, 85-88 | 0.05 | Timing and substitution |
| P63 | Procedural chain and residual fact findings | Fatigue was not shown materially to impair the master's decisions; the successive dismissals form one procedural chain rather than separate payment or refund events; and the sounding corrections were already marked on the working chart (3 checkpoints) | F46, F50, F51; first instance paras.117, 123-124, 129, court of appeal para.76, final judgment paras.30, 33, 146 | 0.05 | Authority reconciliation |
| P66 | Basis of the contributing interests | Freight is fully earned and carried inside the cargo value rather than as a separate interest; the two shipper-owned containers sit in cargo while the equipment value covers the other boxes; the bunker value is remaining plus discharged-and-not-reloaded fuel, less voyage consumption, plus the amount made good (3 checkpoints) | F01, F02, F03; adjustment pp.9, 50 | 0.08 | Contributing-interest basis |
| P67 | Schedule roll-forward | The schedule rows themselves carry the roll-forward after the gross section totals: remainder USD 125,462.17, admitted principal USD 11,805,532.18, pre-fee subtotals USD 12,541,572.04 and USD 12,743,511.08, and final funds USD 13,407,562.70 and USD 13,609,501.74, each figure with its stage named in the row or its column header (6 checkpoints) | adjustment pp.89-92 | 0.07 | Roll-forward |
| P65 | Operational disposition and security status | Collection of the dismissed respondent claim stops while the quantum schedule is retained and securities are reconciled; security-collection status is not contribution-payment status; and the security and administration costs stay in the issued historical allowance ledger (3 checkpoints) | F20, F34, F38; adjustment pp.7, 9-10, 83-92, final judgment paras.20-21, 146 | 0.05 | Settlement boundary |

Every checkpoint in the table is a determination — the checkpoint an `F`-number
identifies — and is earned when one passage of the deliverables carries all of that
determination's required elements together — its subject, the amounts or rule
references it turns on, and the direction of its conclusion — each element satisfied
by any one of its accepted alternatives. A passage is a line, a paragraph, a window
of up to four consecutive lines, or a schedule row read with its header row, so a
determination may be spread across a short run of lines or across a row and its
column names. A determination is read only where the page or paragraph pinpoint it
rests on is visible with it.

Partial credit is the rule: an item with several checkpoints earns the share it
satisfies, so a partially covered finding register scores between 0 and its weight.
No item requires a particular heading, filename, row order or fixed phrase.

### Accepted equivalent expressions

- Pinpoint conventions: `p. 50`, `pp. 89-95`, `page 7`, `para. 129`, `para 118`,
  `paras 145-146`, `paragraph 11-14`, `¶ 76`, and the neutral-citation bracket
  `[146]`. A pinpoint carried in a Markdown footnote definition counts for the
  sentence that references it; the carrier is not scored, the pinpoint is.
- Level and amount notation: `USD 11,805,532.18`, `11,805,532.18`, `11805532.18` and
  `11.805.532,18` are the same figure; `2%` and `2 %` are the same rate.
- Case, full-width characters, en dashes, em dashes and minus signs, and runs of
  whitespace are normalised before matching.
- Terminology: any clear wording that preserves the same relationship is accepted —
  `remainder` or `outside general average` or `not admitted`; `admitted` or `general
  average` or `allowed`; `non-delegable` or `answers for` or `cannot escape`;
  `intermediate appeal` or `court of appeal`; `box` or `container`; `fuel` or
  `bunker`. For the A6a split (P12) each amount keeps its own role: USD 5,011.91
  labelled general average and USD 10,023.81 labelled remainder is the split reversed
  and does not earn the checkpoint.
- A clause that poses a question, or that reports what a party argued, contended,
  pleaded or submitted, is read as attribution rather than as the deliverable's own
  assertion — which is how the review is expected to record the owners'
  uncharted-shoal account and the other pleaded alternatives.

## Deductions

Each damage instance multiplies the score by its coefficient.

| Item | Error | Damage instances | Coefficient | Rationale |
| --- | --- | --- | --- | --- |
| D01 | A supplied source record no longer matches the immutable copy the review is written against | once | 0.1 | The deliverables were produced against altered materials, so no conclusion in them is anchored to the supplied record |
| D02 | The memorandum is missing or empty | once | 0.1 | The primary deliverable was not produced |
| D03 | The memorandum is present but the schedule is missing or empty | once | 0.3 | The auditable roll-forward the instruction requires was not produced |
| D04 | Exactly one operative determination is asserted against the supplied record | once | 0.6 | A reversed determination is the wrong answer however faithfully the rest is reproduced |
| D05 | Two or more operative determinations are asserted against the supplied record | once | 0.4 | Several reversed determinations leave the review unusable as a statement of the position |
| D06 | A required unit is missing with its key value: in the schedule, each of the four interests' contributory value and contribution, the contributory capital, the apportioned claim, the two contract populations' value and fund, the gross of sections A and D, section C admitted, the gross ledger total, the Rule XX commission, the two Rule XXI interest amounts and the adjustment fees; in the memorandum, the pinpointed findings F01, F07, F12 and F27 and the voucher B5 remainder and admitted amounts | one aggregate missing-unit instance per submission, capped at one | 0.9 | Missing units also lose their own positive coverage; no repeated multiplicative omission penalty |
| D07 | The voucher population is transcribed: 30 or more of the adjustment's 35 vouchers (A1-A7, B1-B14, C1-C3, D1-D11, a sub-voucher counting for its parent) are cited | once | 0.5 | The instruction asks for the affected accounts without transcribing the full voucher population |
| D08 | A conclusion rests on information outside the supplied record (press, news or media reports, industry or market sources, Lloyd's List, public or online reporting), stated rather than negated | once | 0.5 | No conclusion may depend on information not provided in the workspace |

D02 and D03 are alternatives: a missing memorandum is charged instead of, not as well
as, a missing schedule. D06 is read only when the memorandum is present, and a
missing schedule also forfeits every schedule unit. D04 and D05 are alternatives in the same way, so a
deliverable's reversed determinations are charged once as a single instance at the
band its count falls in. The source-integrity, give-away unit, transcription and outside-information
instances are independent of these.

The eight operative determinations the supplied record settles, any one of which
counts once however many phrasings state it, are: the owners do not obtain the
respondent cargo interests' contribution; the owners' appeal was dismissed and the
first-instance order stands; the vessel was unseaworthy; the causative want of due
diligence was actionable fault and was not discharged by entrusting the work; the 8%
cash call was provisional security rather than the operative debt or rate; the issued
adjustment stays as the historical quantum record rather than being re-cut on a
corrected basis; the supplied records do not establish that every cargo contribution was
paid; and the supplied records do not determine refunds or a blanket
release of securities. Each is tested as its topic together with the outcome
vocabulary that would state the opposite, read against the negation of its own
clause, so stating the determination correctly in any wording asserts none of them.
Wrapped lines are rejoined before sentences are cut, so a negation split across two
physical lines still governs its sentence.

Interactions with the positive items: a deduction never zeroes an item directly, but
a deliverable that is missing also forfeits the checkpoints it would have carried —
the schedule is read alongside the memorandum, and a determination stated in a
schedule row is read with that row's header row.

## Automatic Failure

There is no automatic failure for formatting alone. A submission with no readable
deliverable earns no item credit and scores 0. Every other penalty is a multiplicative
deduction rather than a score cap.

## Lenient Lens

A 0/1 lens is reported next to the strict score and settled from the strict scorer's
own per-item results, never from the weighted total. It is 1 when every one of these
holds, else 0: no D01, D02, D03, D04, D05 or D06 instance was raised (the supplied
records are intact, both deliverables exist, no operative determination is reversed
and no give-away unit is missing), no D07 or D08 instance was raised (the deliverable
does not transcribe nearly the whole voucher population and does not base a
conclusion on outside information), and P52 (deposit call versus final rate), P41
(rule routing of the allowance classes) and P38 (no account-level order in the
dismissal) are each earned in full. Coverage of the wider finding register, ledger
and pinpoints is left to the strict score.

## Evaluator Interpretation

Professional maritime and legal findings are adjudicated from the supplied record
with exact candidate quotations. Equivalent terminology, including `GA`/`PA`,
`box`/`container`, `%`/`percent`, and `p.`/`§`/`para.` locator conventions, is
accepted when the candidate adopts the complete finding. A party submission,
question, rejected argument, negated proposition or disconnected term cluster is not
adoption. Amounts, formulas, source hashes and source locators remain deterministic.

D06 is one aggregate damage instance per submission because its missing mandatory
units already lose their positive credit; multiplying 0.9 once reflects the added
loss of audit usability without repeatedly charging the same omission. D07 and D08
are independent 0.5 instances because either a near-complete source transcription or
an externally founded conclusion materially defeats the issued brief while leaving
the independently correct arithmetic measurable. The commission bridge preserves
the printed USD 226,130.84 and discloses that USD 11,306,541.09 multiplied by 2%
rounds to USD 226,130.82, a USD 0.02 source discrepancy pending clarification.
