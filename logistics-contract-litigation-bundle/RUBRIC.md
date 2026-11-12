# Scoring Rubric — logistics-contract-litigation-bundle

The deliverable is scored by the deterministic program judge and the request-bound
semantic judge in `tests/`. The program layer owns files, structure, arithmetic,
source-closed facts, and explicit damage. The semantic layer uses the unified
`gpt-5.6-sol` judge only for professional equivalence, source fidelity, polarity,
and scope; it cites exact candidate evidence and never supplies missing facts.
Replay mode uses the packaged request/response cache, while fresh mode measures a
new artifact with the same public context.
Deliverable: `workspace/output/`.

## Score Form

```text
program_strict  = positive_earned * retention
positive_earned = sum over the positive items of weight * completion   (weights sum to 1)
retention       = product over distinct damage instances of that instance's coefficient
```

Completion is a value in [0, 1] per item: the item's value has to be stated, in this deliverable's own words, inside the scope the item names; an item built from several checks takes the share of them that hold. Weights and coefficients are read from `tests\rubric-contract.json`; this document states the same numbers.
Manifestations that share one damage instance are charged once, at the smallest coefficient among them, so one mistake written three times costs what one mistake costs.

## Scoring Dimensions

| Dimension | Weight | Items |
| --- | ---: | --- |
| Content | 1 | P01, P02, P09, P10, P11, P12, P13, P14, P15, P16 |

### Content (1)

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P01 | The complaint states the supported parties, forum, contract, notice dispute, takeover, and resulting loss of the operating right. | the adopted complaint DOCX | 0.05 |
| P02 | The complaint adopts a source-supported and internally coherent remedial route. Restoration/performance, return of the operating right, or termination with supported consequential relief are accepted professional choices. | the adopted complaint DOCX | 0.05 |
| P09 | The evidence list includes the four supplied evidence groups and assigns bounded, source-appropriate proof purposes. | the adopted evidence_list DOCX | 0.06 |
| P10 | The handoff record captures the dispute, client objective, core timeline, and received evidence inventory. | the adopted case_handoff DOCX | 0.05 |
| P11 | The service confirmation carries the two parties' names and the supported service address and telephone. | the adopted service_form DOCX | 0.05 |
| P12 | The refund confirmation identifies both plaintiffs. | the adopted refund_form DOCX | 0.05 |
| P13 | The five-document set is complete and uses one consistent party, contract-date, dispute, amount, and evidence identity. | the adopted all DOCX | 0.05 |
| P14 | The evidence list includes all four supplied source groups. | the adopted evidence_list DOCX | 0.07 |
| P15 | The current evidence list does not present unprovided future evidence as part of the filed inventory. | the adopted evidence_list DOCX | 0.27 |
| P16 | The refund confirmation carries Yi Zejie as the intended payee without inventing bank details. | the adopted refund_form DOCX | 0.3 |

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | An adopted filing uses a materially different contract date, defendant, operating-right object, or agreed RMB 100,000 anchor. | litigation:wrong-contract-anchor:one independent business harm | 0.9 |
| D02 | — | An adopted filing reverses the parties and states that the plaintiffs' admitted breach is the case's operative conclusion. | litigation:reversed-breach-actor:one independent business harm | 0.9 |
| D03 | — | A notice allegation such as unlawful personal collection or tax evasion is adopted as an established plaintiff fact without attribution or dispute status. | litigation:adverse-allegation-as-fact:one independent business harm | 0.7 |
| D04 | — | The filing set affirmatively invents a court-assigned case number or a bank account not supplied in the record. | litigation:fabricated-official-field:one independent business harm | 0.9 |
| D05 | — | Two adopted deliverables assign conflicting dates, amounts, party roles, or outcomes to the same core event. | litigation:cross-document-contradiction:one independent business harm | 0.9 |
| D06 | — | A requested filing is replaced by a source dump, keyword spray, or grossly mismatched document shape rather than a usable filing. | litigation:unusable-deliverable-shape:one independent business harm | 0.7 |
| D08 | — | The adopted prayer requests additional damages or a refund while leaving the requested amount as an unresolved blank, so the complaint is not filing-ready. | litigation:unliquidated-monetary-prayer:one independent business harm | 0.9 |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

The mixed judge settles the published strict value from the two independently
owned layers:

```text
reward_strict = 0.70 * program_strict + 0.30 * semantic_score
```

There is no target cap or score floor. Strict is a direct weighted sum: the
program layer contributes 70% for file roles, explicit source anchors,
cross-document controls, and deterministic damage evidence; the source-bound
LLM layer contributes 30% for requirement coverage, source fidelity, polarity
and status, and object/scope binding. Open legal meaning and equivalent
professional expression therefore cannot be settled by keyword matching alone.

Within the semantic layer, source fidelity carries 50%, requirement coverage
20%, polarity/status 15%, and object/scope binding 15%. Source fidelity is the
largest semantic component because a litigation filing that looks complete but
turns unsupported details into adopted facts creates the principal professional
risk. Coverage remains independently measured, while polarity and scope protect
against reversing disputed allegations or attaching a fact to the wrong party,
document, or evidentiary purpose.

## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Lenient Lens

`reward_lenient` is a separate 0/1 usability gate. It is 1 only when all five
requested filings are present; the complaint contains an adopted request and a
source-backed factual basis under ordinary equivalent headings; the four
supplied evidence groups are listed without presenting future evidence as
already filed; unsupported refund fields remain pending; the remedial route is
coherent; and no adopted critical damage finding is present. These are business
readiness conditions, not a cap on `reward_strict`; partial strict credit remains
visible when the gate is 0.


Capability tags: source-grounded litigation analysis; pleading accuracy; evidence mapping; filing-package consistency.
