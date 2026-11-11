# Scoring Rubric — cross-examination-defendant-enforcement-objection-action

The deliverable is scored by deterministic checks plus the required evidence-bound semantic judge described below. The judge sees the supplied case record and deliverable, with no access to the agent trajectory or identity. Cached verdicts are bound to model, rubric, source and candidate.
Deliverable: `artifacts/质证意见.docx`.

The actor instruction does not enumerate these criteria or the method used to satisfy them. With-skill and no-skill candidates are scored by this same condition-blind contract.

## Score Form

```text
final           = positive_earned * retention
positive_earned = sum over the positive items of weight * completion   (weights sum to 1)
retention       = product over distinct damage instances of that instance's coefficient
```

Completion is a value in [0, 1] per item: the item's value has to be stated, in this deliverable's own words, inside the scope the item names; an item built from several checks takes the share of them that hold. Weights and coefficients are read from `tests/pjroot/rubric-contract.json`; this document states the same numbers.
Manifestations that share one damage instance are charged once, at the smallest coefficient among them, so one mistake written three times costs what one mistake costs.

## Scoring Dimensions

| Dimension | Weight | Items |
| --- | ---: | --- |
| Content | 1 | P01, P08, P12, P13, P14, P15, P16, P17, P18, P19, P20 |

### Content (1)

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P01 | the first court document among the plaintiff's exhibits is the (2025)某执异XXX号 enforcement ruling; scored deterministically | the evidence-detail region | 0.0715 |
| P08 | exhibits 4 to 6 do not establish specification and control of the attached money sufficient to resist execution | the opinion on exhibits 4 to 6 | 0.195 |
| P12 | the document is issued by the defendant B公司 | the caption and the signature block | 0.039 |
| P13 | exhibits 2 and 3 are the identified court enforcement instruments and receive the supported authenticity/lawfulness stance; identity is deterministic (50%), stance semantic (50%) | opinions on exhibits 2 and 3 | 0.078 |
| P14 | exhibit 4 identity plus its limited proof of registration arrangements; identity is deterministic (40%), analysis semantic (60%) | opinion on exhibit 4 | 0.0455 |
| P15 | exhibit 5 identity plus the gap between contractual custody and actual control; identity is deterministic (40%), analysis semantic (60%) | opinion on exhibit 5 | 0.0455 |
| P16 | exhibit 6 identity plus the limit of registration/publicity for tracing the debited money; identity is deterministic (40%), analysis semantic (60%) | opinion on exhibit 6 | 0.0455 |
| P17 | actual bank-flow analysis: mixed inflows, uses and their implications for fund specificity | exhibit 7 | 0.130 |
| P18 | reconcile the visibly different masked account identifiers (`****_1` in execution instruments versus `****` in registration, custody and transaction records) and state the unclosed account-identity consequence | opinions on exhibits 2 to 7 | 0.120 |
| P19 | identify the five incorporated but unprovided registration attachments and limit the complete registered-collateral scope accordingly | opinion on exhibit 6 | 0.100 |
| P20 | address the partly illegible pledge-contract number and the stated `45,589.00` collateral value as limits on treating the registration as coverage of the `15,839,770.26` debit | opinion on exhibit 6 | 0.130 |

The positive weights follow legal consequence and evidentiary dependency. P08
receives 0.195 because the specification-and-control analysis is the principal
merits objection across exhibits 4-6. P17-P20 jointly receive 0.48 because bank
flow, account identity, missing incorporated attachments and the illegible
contract/value boundary determine whether the plaintiff can trace the disputed
funds; each is independently necessary and source-limited. P13 receives 0.078
for the court-instrument identity and stance, while P14-P16 receive 0.0455 each
for exhibit-specific identity plus a bounded evidentiary conclusion. P01 and
P12 receive 0.0715 and 0.039 as deterministic orientation controls: they are
necessary to read the filing correctly but do not substitute for the merits
analysis. The allocations are relative professional-risk shares, not pass
thresholds; multi-part owners award their documented completion fraction.
Missing content loses only its positive share, while an affirmative harmful
position is handled separately by the damage owner below.

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | Party stance inverted | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.2 |
| D02 | — | Misled by the superseded exhibit list inside the Materials | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.7 |
| D03 | — | Self-defeating concession of the plaintiff's case | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.5 |
| D04 | — | Specific facts the Materials do not establish | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.7 |
| D05 | — | Baseless denial of a court instrument | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.1 |
| D07 | — | A request for substantive judgment inside an evidence opinion | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.3 |
| D08 | — | Evidence opinions silently missing for whole exhibits | item plus ordinal of the instance (missing_opinion:1, missing_opinion:2), one instance per two missing exhibits, capped at 2 | 0.8 |
| D09 | — | A statutory provision relied on for a proposition its chapter does not govern | item plus law id and article number (miscited_provision:民法典:688); repeated reliance on the same provision is one instance | 0.7 |
| D10 | — | Deliverable not delivered as the Word document the brief names | item plus the constant object delivery_path: one instance | 0.7 |

### Deduction owner rationale

Coefficients are retention values, not weights or caps: 0.1 retains 10% after a near-fatal affirmative error; 0.8 retains 80% after a material but locally curable omission. Independent damage objects multiply; repeated manifestations of one object merge.

| Owner | Professional harm, dependency and coefficient rationale | Why omission is different |
| --- | --- | --- |
| D01 | Inverts the represented party's stance, defeating the document's purpose; coefficient 0.2 reflects near-fatal wrong-side advocacy. | Missing a stance loses its P owner/D08; it does not affirm the opponent's case. |
| D02 | Uses the superseded embedded list as this suit's evidence; coefficient 0.7 because the affected identities lose their positives and the remaining correctly segmented analysis can survive. | An unidentified item loses positive credit; substitution affirmatively points analysis to the wrong object. |
| D03 | Concedes the plaintiff's dispositive theory; coefficient 0.5 reflects serious self-defeat while preserving unrelated correct evidence opinions. | Silence is incomplete, not a concession. |
| D04 | States specific transactions or facts absent from the record; coefficient 0.7 because the false detail is local and independently sourced correct analysis remains useful. | Careful limitation or omission is preferable to invention. |
| D05 | Baselessly denies a court instrument; coefficient 0.1 because attacking an official act without ground destroys credibility and the supported procedural stance. | Omitting an authenticity stance loses P13/D08 but does not make a false accusation. |
| D07 | Requests merits relief inside an evidence opinion; coefficient 0.3 because it exceeds the filing's procedural function and can make the requested disposition unusable. | Omitting a closing request is incomplete but does not ask for impermissible relief. |
| D08 | Silently omits opinions for whole exhibits; coefficient 0.8 per two missing exhibits, cap 2, because each batch is curable and the completed opinions retain value. | Individual missing positive content is not false; D08 measures only batch-level coverage harm beyond the lost positives. |
| D09 | Relies on a provision for a topic its chapter does not govern; coefficient 0.7 because the bad citation is local, repeated citation of the same provision is one instance, and correct evidence analysis survives. | No citation is not penalized unless a legal rule is necessary for a scored positive; D09 only addresses an adopted wrong authority. |
| D10 | Uses the wrong carrier/path; coefficient 0.7 when readable elsewhere, while a missing required deliverable is separately zeroed by the delivery gate. | Content omission is handled by P/D08; delivery form is an independent contractual defect. |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Delivery Gate

Applied by `tests/deliverable_gate.py` before the score is settled, on the files directly under `artifacts/`:

- **Missing deliverable.** `质证意见.docx` must be present under that exact name; if any is missing the score is 0.
- **Extra files.** Every other file there that is neither required nor allow-listed (`manifest.json`; hidden files and caches are always allowed) is one damage instance of `DX_DELIVERABLE` at coefficient 0.4, at most 2 instances.
- **Source pasted in.** A run of at least 500 normalized characters copied verbatim from a materials document into a required deliverable is one damage instance of `DX_SOURCE_DUMP` at coefficient 0.4, at most 2 instances; quoting the source is not charged.

## Lenient Lens

`reward_lenient` is a legal-usability gate, independent of the continuous score. It is 1 only when P12 identifies B公司 as the issuing party, at least one of P08 or P17 supplies a case-bound merits objection, and none of D01, D02, D03, D04, D05, D07 or D10 is triggered. Those deductions identify an inverted stance, substitution of the decoy exhibit list, a self-defeating concession, fabrication, baseless denial of a court instrument, an out-of-scope merits request or a wrong delivery carrier. Missing opinions and a miscitation remain in `reward_strict` when the core defense is still intelligible; their count or coefficient does not decide this binary gate.

## Semantic Adjudication

An evidence-bound OpenAI Responses GPT judge evaluates P08/P17-P20, the analysis portions of P13-P16, and final review of D03/D09 in whole-paragraph context. P01, P12, exhibit identities and the remaining affirmative-error checks are deterministic. The D03 and D09 deterministic scans only nominate candidate passages; they cannot impose damage when the semantic review finds no adopted concession or incompatible legal reliance.

`tests/golden_replay/` contains one response keyed by the unchanged Golden's complete request. Every other candidate requires `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY` (plus optional `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, `LLM_JUDGE_TIMEOUT_SECONDS` and `LLM_JUDGE_REASONING_EFFORT`). `auto` uses an exact replay before live service, `replay` forbids live fallback, and `live` bypasses replay. Missing service, a replay miss in replay mode, or invalid evidence is UNMEASURED rather than a business zero.
