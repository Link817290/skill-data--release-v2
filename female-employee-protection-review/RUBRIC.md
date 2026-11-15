# Scoring

The scorer reads the editable Office report, review workbook and action workbook together with the supplied dated materials.

| Domain | Weight |
| --- | --- |
| zhou_current | 0.08 |
| he_historical | 0.02 |
| he_current | 0.06 |
| chen_payroll | 0.05 |
| chen_calendar | 0.05 |
| chen_benefit | 0.15 |
| chen_postreturn | 0.18 |
| zhao_current | 0.05 |
| zhao_historical | 0.03 |
| wang_contract | 0.05 |
| wang_nursing | 0.20 |
| delivery_controls | 0.08 |

Each domain retains its independently measured substantive partial abilities. Whole-period, cross-file and functionally equivalent actions are accepted; names, exact row layouts, repeated dates and optional training formats are not independent positive requirements.

The weights emphasize current protection decisions, evidence-bound conclusions and executable follow-up. Chen's benefit reconciliation and post-return controls receive 15% and 18% because they govern payment, work-time and night-work consequences; Wang's nursing-period contract disposition receives 20% because an incorrect adopted action can terminate employment during a protected period. The remaining current reviews and delivery controls receive 42%, while the two historical verification responsibilities receive 5%. No individual binary predicate owns these domain weights: each domain is settled from its disclosed analysis, source and action components. Within a review unit, analysis, source support and accountable action contribute 50%, 25% and 25%; these are additive so a missing support component loses its own share without erasing completed work.

Let `B` be the weighted completion sum. Strict reward is `max(0, B-D)`. `D` sums unique causal events: `0.15` per blocking operation or rights-depriving decision and `0.03` per nonblocking factual error. Repeated manifestations of one causal error are charged once, while independent errors continue to reduce the score. There is no exponent, retention floor or score cap.

The known-error status correction, unsupported current-stage analysis correctness and adopted final-output clock predicates use exclusive error ownership. Independent omissions stay missing; adding an unsupported assertion does not fill an omitted historical or clinical inquiry. Repeated copies of one error do not create extra events.

Lenient reward is independently binary minimum usability across the five current employee reviews, essential evidence safety, and accountable open controls. It is not a strict-score threshold and does not require every strict historical or September detail.

The package includes one hash-bound Golden replay containing the qualified provider request, response, decision and validation. A changed candidate cannot use that replay and requires fresh evaluation through `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY`; fresh responses are written only to the externally configured verifier cache. Technical failures return nonzero without writing a business score.
