# Recruitment Package Rubric v3.4

## Scope and authority

This contract scores the four publication files named in `task/instruction.md`. The
instruction, the approved role brief, the professional directory, and the source
authority records are the controlling inputs. Candidate resumes are background
evidence only; they never define a public eligibility rule.

The only identity exception is **U019**: the directory publisher's attachment number
and year are metadata, not an applicant-facing proposition. They receive no positive
credit and no deduction. All other adopted statements are evaluated against the
instruction. A stale template, an expanded blacklist, a broader talent pool, an
unauthorized role requirement, or a blanket full-time requirement is a real content
defect, not a Golden waiver.

## Shared scoring protocol

Both strict and lenient views use the same extracted evidence, item IDs, weights,
equivalence rules, and deductions. The lenient view is a binary release diagnostic;
it does not cap or rescale strict quality.

```text
positive_earned = sum(item_weight * fulfilled_fraction)
deduplicated_deductions = sum(maximum charge for each root_key and harm_unit)
strict = max(0, positive_earned - deduplicated_deductions)
lenient = 1 iff all four files parse, the package is structurally closed,
          positive_earned >= 0.50, and no unresolved evidence remains; else 0
```

There is no strict-score cap, floor, target clamp, or forced score band. Omission of a
normal statement loses only its positive credit. A material wrong statement is charged
only when the contract identifies an independent harm. Repeated evidence for one root
and harm unit is deduplicated.

Every decision records the output hash, exact file or cell location, object/role,
condition, period, adoption status, and reason. Wording, paragraph order, Chinese
punctuation, equivalent date notation, and table-versus-prose presentation remain open
when the business relation is preserved. Semantic review uses the same six
`LLM_JUDGE_*` variables as the task configuration; it may recognize an equivalent
relation but may not invent an item or override a mechanical gate.

## Positive items

The weights sum to `1.000000`. The values reflect independent applicant-facing
decisions: professional authority, hierarchy direction, evidence-bounded discretion,
privacy/source separation, form minimization, and attachment closure. P04 and P12 are
not duplicate checks: one prevents a specific profession from expanding upward, while
the other prevents a directory-listed profession outside the adopted role scope from
being treated as eligible.

| ID | Weight | Required relation and professional reason |
|---|---:|---|
| P01 | 0.2192 | Bind professional identity to the applicant's diploma/credential and the adopted directory basis. A resume or employer label is not an authority. |
| P02 | 0.0900 | Apply the economics-and-management discipline group at the same directory hierarchy level to both role records; do not replace it with an unapproved narrower list. |
| P03 | 0.2193 | Route an unlisted profession to recruiting-unit review using application materials and courses, with neither automatic acceptance nor automatic rejection. Full credit requires the evidence-bounded route; review authority without an evidence basis is half credit. |
| P04 | 0.1189 | State the logical direction that a named specific profession does not automatically admit its broader class or discipline group. |
| P12 | 0.1087 | Distinguish directory inclusion from role eligibility: a listed profession outside the role's adopted scope is not sufficient. |
| P05 | 0.0172 | Keep candidate resumes as background records; no candidate career proposition becomes public policy, duty, qualification, or operation. |
| P06 | 0.0218 | Remove candidate direct identifiers from all visible public surfaces. |
| P07 | 0.0158 | Remove candidate/referee identifiers from metadata, comments, hidden workbook surfaces, links, drawings, and embedded objects. |
| P08 | 0.0454 | Use a minimal signable commitment covering truthful, accurate, complete submitted information/materials, consequences, signature, and date, without requesting identity number, phone, or email again. |
| P09 | 0.0232 | Resolve the notice's position-schedule attachment to exactly one usable record for each role. |
| P10 | 0.0591 | Resolve the notice's commitment attachment to a substantive signable form. |
| P11 | 0.0614 | Close the typed graph from notice to schedule, directory payload, and commitment, with no orphan or role swap after U019 identity removal. |

Partial credit is allowed only for P03 as stated above. Headings, copied source
fragments, keyword piles, blank containers, or a single material do not earn positive
credit. A changed carrier (`.doc`, RTF, HTML-in-DOC) is neutral when it is parseable and
the publication payload is preserved.

## Atomic deductions

The following deductions are additive and uncapped. Each has a professional basis and
an independent harm unit; a semantic judge must confirm the adopted relation when the
mechanical detector produces a candidate.

| ID | Scale | Trigger |
|---|---:|---|
| D01 | 0.25 | Candidate direct identifier disclosed, per person and identifier class. |
| D02 | 0.20 | Referee/proof person's name or contact disclosed, per referee. |
| D03 | 0.15 | Candidate-specific employer, project, award, performance, or career claim adopted as policy/duty/qualification. |
| D04 | 0.06 | Commitment requests identity number again. |
| D05 | 0.04 | Commitment requests personal phone again. |
| D06 | 0.04 | Commitment requests personal email again. |
| D07 | 0.12 | Role professional scope is broadened, narrowed, or bound to the wrong hierarchy/role. |
| D08 | 0.10 | Unlisted profession is automatically accepted or rejected without recruiting-unit review. |
| D09 | 0.08 | Experience cutoff differs from 2026-09-15 or ignores complete years/months. |
| D10 | 0.08 | Full-time-study internships, part-time work, or social practice are counted as qualifying experience. |
| D11 | 0.10 | General Manager management alternatives are changed from OR to AND. |
| D12 | 0.10 | One General Manager alternative drops a required duration, institution/role class, or additional experience condition. |
| D13 | 0.08 | General Manager age boundary differs from the inclusive 1976-09-01 boundary. |
| D14 | 0.08 | Business Officer age boundary differs from the inclusive 1991-09-01 boundary. |
| D15 | 0.08 | Application interval is wrong or stage-boundary terms are mixed with review. |
| D16 | 0.08 | Online review interval is wrong or stage-boundary terms are mixed with application. |
| D17 | 0.07 | Later updates are redirected to the wrong channel or applicants are promised separate notice contrary to the settled channel. |
| D18 | 0.12 | Unauthorized written test or other examination stage is adopted. |
| D19 | 0.10 | Initial/final score threshold or advancement ratio is wrong. |
| D20 | 0.10 | Drug-test, retest, or physical-examination rule is materially contradicted. |
| D21 | 0.07 | Replacement is not score ordered, exceeds one replacement, or binds to a later stage that has not occurred. |
| D22 | 0.07 | Publicity period, reporting identity, or unresolved-report disposition is wrong. |
| D23 | 0.08 | Organizer-approved coaching, named preparation books, or application fee is adopted. |
| D24 | 0.08 | Examination-misconduct blacklist duration is wrong. |
| D25 | 0.05 | A required functional notice section is absent when no equivalent section is identifiable. |
| D26 | 0.03 per independently identified burden | The source-bound semantic review confirms materially repetitive, irrelevant, or review-burdening content. Character count relative to Golden is diagnostic only and cannot trigger this deduction by itself; necessary expression of eligibility and process conditions is allowed. |
| D27 | 0.04 | A frozen shape unit falls below its declared minimum and loses the functional section. |
| D28 | 0.10 | Schedule rows are ambiguous, merged, or unusable. |
| D29 | 0.08 | Position-schedule graph edge is absent, orphaned, or wrong. |
| D30 | 0.08 | Commitment graph edge is absent, orphaned, or wrong. |
| D31 | 0.08 | Directory payload graph edge is absent or resolves to the wrong document type. |
| D32 | 0.12 | One distinct unsupported adopted eligibility, process, collection, source-role, or stale-template proposition. Examples include the old full-time blanket, nonattendance blacklist, all-interview talent-pool expansion, unauthorized Business Officer requirements, and the 2023 external-recruitment commitment template. Supported details, tentative options, quotations, rejected examples, and U019 identity tokens are excluded. |

One wrong date or stage is charged under D15/D16, not again under D32. One broken
attachment edge is charged under D29-D31, not again under D32. A local parser failure
is `evidence_insufficient`, never a business deduction.

## Shape and release boundaries

Shape units S01-S08 count normalized visible characters in their bound section/cell
family. The Golden reference values and tolerance bands are implemented in
`task/tests/package_score.py`. Upper-band overrun is supplied to the semantic
review as a diagnostic for D26 and does not itself deduct; D27 continues to detect
a section too short to carry its function. Shape never earns positive credit.

Golden and Oracle must be byte-consistent in business payload and must score `1/1` in
both views after dynamic verification. The final package contains only the release
surface, has no rollout or local audit artifacts, and can be built and scored from a
cold clone using the declared base image and packaged judge cache. Historical rollout
records are calibration evidence, not package inputs.
