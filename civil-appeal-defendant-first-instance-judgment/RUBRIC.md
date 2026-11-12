# Civil Appeal Scoring

Submission: `/workspace/artifacts/civil-appeal-petition.md`. Strict reward is weighted substantive completion multiplied by the retention coefficients of independent affirmative professional errors. Lenient completion is assessed independently of the strict total. Both conditions use the same scorer.

| Item | Substantive requirement | Weight |
| --- | --- | ---: |
| P01 | Scope the appeal to plaza principal193440 and its interest, preserve admitted G/B interest1222.19, and address the separately ordered preservation fee1543 | .05 |
| P03 | Concrete supported disposition with request-ground closure: state an ascertainable substituted result, or revoke and remand while identifying the unresolved scope/price/quality/handover facts | .10 |
| P04 | Explain why preliminary quotation is not agreed settlement, using course of dealing or absence of plaza contract/settlement | .22 |
| P05 | Connect the partial-noncompletion defence to the contradictory no-objection finding and unexamined construction scope | .30 |
| P09 | Challenge April21 handover inference using actual evidence and its limits | .07 |
| P11 | Apply actual-delivery interest rule and support the proposed date or seek verification of actual handover | .16 |
| P13 | Explain claimant completion-scope burden and erroneous shift or limits of photographic proof | .05 |
| P14 | Explain unexamined/summarily rejected quality defence, its possible effect on price, and the principal/remand relief it supports | .05 |

The allocation follows the appellate decision chain. The amount branch carries
57% (P04, P05 and P13) because the central dispute is whether the preliminary
quotation and incomplete-work evidence can support the awarded principal. The
handover-and-interest branch carries 23% (P09 and P11) because an unsupported
handover date changes the accrual period but does not replace the principal
analysis. Operative relief carries 10% (P03), and the remaining 10% protects
scope control and the separate quality/remand consequence (P01 and P14). These
shares express the relative legal work needed to overturn or delimit the
judgment; they are neither fitted to a target score nor a hidden pass line.

Each positive uses atomic `0`, `.5` or `1` credit. For P04, quotation-not-settlement without the course-of-dealing/no-settlement record anchor earns `.5`; the record anchor alone earns `0`. For P05, either the recorded contradiction or the unexamined-scope consequence earns `.5`, and both earn `1`. A required evidence-bound LLM assesses professional meaning, strategic alternatives and adoption status using exact candidate and source quotations. Connected reasoning may cross paragraphs, but each causal limb needs its own entailing evidence. No Golden wording, local-span match, document length, page count or automatic May date is required.

P03 does not reward a bare request to remand or a direction to "determine the actual amount." Full credit requires a disposition supported by the present evidentiary posture, identification of the operative principal/interest at issue, the facts that must be established, and forward/backward closure between requests and grounds. Where the record cannot support a concrete substituted amount or date, revocation and fact-specific remand is the concrete relief.

Request-ground closure is read across the requests and connected grounds, not from one line alone. A short request to remand can earn full P03 when the grounds identify the unresolved basic facts and explain why the present record cannot support a substituted result. Unsupported total dismissal, bare remand with no identified facts, or a quality/amount/date ground that feeds no requested disposition makes P03 incomplete and fails `C_RELIEF` when the filing is not usable as a whole. P14 separately measures whether the quality ground is examined, connected to its potential price effect, and carried into principal/remand relief.

Fixed facts and arithmetic remain mandatory: quotation194970 minus already deducted installation1530 equals award193440; defendant estimated completed work at7–8万元, not a settled liability; court selected2025-04-21; G/B principal743500 was paid in two371750 instalments and its1222.19 interest was admitted. April16 unfinished door/window does not prove April21 incompletion. May acceptance is distinct from actual handover. Display-screen installation was excluded from quotation and the design changed to white wall; no invented automatic price reduction follows.

The judgment appendix supplies Civil Code577/579 and Construction Interpretation(I)9,26,27. Article27 starts interest from actual handover where delivered; its un-delivered-work alternatives do not authorize disregarding defendant's admitted May use. Current Civil Procedure Law177 permits ascertain-and-amend or remand for unclear basic facts. Unknown identifiers and dates must remain visibly unspecified. Source-supported legal arguments and relief may differ from the reference; invented facts, wrong arithmetic and incorrect rules are not equivalent alternatives.

| Error | Coefficient | Damage unit |
| --- | ---: | --- |
| D01 party/role inversion | .3 | one role error |
| D02 appeal scope reaches admitted interest/whole judgment without support | .9 | one scope error |
| D03 adopt adverse quotation/completion or April21 delivery conclusion | .5 | amount and date are separate causes |
| D04 misstate record figure/date or reverse the April16 speaker attribution | .7 | each independent record-fact cause |
| D05 wrong appellate court | .7 | one court error |
| D06 fabricated identifier, person or unknown exact date | .8 | one fabrication cause |
| D07 repealed/superseded legal basis | .8 | one obsolete basis |
| D13 wrong article or false attribution of court/appellee legal basis | .7 | up to two distinct legal miscites |
| D14 invented first-instance appraisal application | .7 | one unrecorded procedural fact |
| D15 lawyer/client drafting notes in filing | .7 | one audience error |
| D16 own-record contradiction: never-delivered, suit-date interest, fully satisfied debt, or total non-liability despite the admitted partial value | .7 | one contradictory position |
| D17 missing filing skeleton: parties/court/requests/reasons | .4 | missing parts, capped at two |
| D11 appended summary repeating argued grounds | .9 | one repeated closure |
| D12 asserted unprovided enclosure inventory | .5 | one inventory |

Repeated manifestations of the same specific causal claim are charged once. D03_AMOUNT and D03_DATE are semantic subtypes of D03, each retaining its .5 coefficient and its distinct amount/date root. D16 covers the separate own-record contradictions. Shared paragraph or quotation locations never merge independent causes; a D16-only proposition does not also trigger D03. An adopted conditional request or legal consequence is assessed for professional correctness. Only quoted, rejected or merely hypothetical views that the author does not adopt are excluded. Ordinary omissions lose their positive credit without an additional affirmative-error charge. D08/D09/D10 length proxies are diagnostic only and cannot deduct. D01 covers actual party-role inversion; a supported alternative request that the appellant pay only the amount ultimately proved is not inversion. D11 requires a separate appended section that repeats grounds; an ordinary unheaded concluding paragraph and character count alone do not trigger. Exact factual, court-role, identifier and legal-article checks remain deterministic; semantic checks handle the remaining professional decisions. Naming the lower court as the author of the attacked judgment or stating that the appeal is submitted through the first-instance court is correct and is never an appellate-addressee error. The machine contract is `task/tests/rubric-contract.json`, with authoritative semantic criteria in `task/tests/semantic_judge.py` and private professional rules identical to the issued skill guidance.

Professional conflicts settle before the strict total. D02 over-scope removes P01 scope credit. D03_AMOUNT removes P04, P05 and P13 and caps P03 at `.5`; D03_DATE removes P09 and P11 and caps P03 at `.5`. These rules prevent a filing from receiving credit for an argument while adopting its opposite. Damage instances then multiply the positive total once per canonical causal root. Independent D03 amount/date roots multiply separately; repeated wording of one root does not. D01, D05 and D17 concern whether the document is a usable appeal filing; D02 concerns scope; D04/D06/D07/D13/D14/D16 concern independent factual, legal or self-contradictory professional errors; D11/D12/D15 concern distinct filing-content errors.

Strict reward is `sum(weight * settled_fraction) * product(independent_damage_coefficients)`. Lenient reward is independently `1` only when `C_FILING`, `C_RELIEF` and `C_MERITS` all pass and no core professional damage is present; it is not a threshold on strict reward. Final `C_MERITS` uses the same settled evidence as strict: at least one amount branch among P04/P05/P13 and one delivery-interest branch among P09/P11 must reach `.5`, and no D03/D04/D06/D07/D13/D14/D16 core merits damage may remain. The raw semantic completion opinion remains in the audit ledger but cannot contradict the settled atomic predicates. D11 repeated closure and D12 unprovided enclosure inventory are local quality defects: they reduce strict but do not alone make an otherwise complete appeal unusable. D15 client-facing drafting notes remain core because they make the delivered filing unsuitable for submission. Record/source reversal (D04), an invented exact delivery day (D06), and total non-liability contrary to the appellant's own partial-value admission (D16) are core merits defects and block lenient. The D04 speaker-attribution subtype requires an explicit wrong role such as `被上诉人员工`, `原告工作人员` or `B公司一方`; an ambiguous generic reference such as `施工方` is not enough for a core penalty. A missing, empty or invalid-UTF8 candidate is measured business output and receives `0/0`. A missing judge credential, endpoint failure, invalid judge schema, permission error or offline cache miss is evaluator infrastructure failure: `test.sh` removes stale reward files, writes `UNMEASURED`, and exits nonzero. Infrastructure failure is never converted into business zero.

The program-judge regular expressions diagnose objective facts only. They do not control P03/P04/P05 professional equivalence. No hidden word-distance, closed verb list or Golden phrase is required: the semantic decision must cite exact candidate and source evidence for each atomic causal limb.

Lenient1 requires a usable Chinese appeal filing (C_FILING), supported operative relief within the record and procedural posture (C_RELIEF), and meaningful source-supported principal and interest arguments without a core professional damage. Local D11/D12 quality defects do not independently defeat usability. These are evidence-based completion decisions, not a strict-score threshold or error-count allowance. Missing/unreadable work receives0. Infrastructure failures follow the `UNMEASURED` boundary above.

`tests/golden_replay/` contains exactly one response keyed by the unchanged Golden's complete source-bound semantic request. It contains no ordinary candidate response, run/provider history or credential and is outside the actor image. Any changed artifact misses it and requires fresh external adjudication; without that service the result is UNMEASURED, never a business zero or Golden reuse.
