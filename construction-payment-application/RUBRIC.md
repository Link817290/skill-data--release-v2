# Construction Payment Application Rubric

## Authority and Measurement

The executable authority is `task/tests/test.sh` and `evaluator.py`. Deterministic
checks own quantities, rates, deductions, balances and cross-file arithmetic. The
source-bound mixed judge owns professional equivalence, authority, handoff and
submission language. Missing judge services, invalid responses and replay misses
are infrastructure errors, not candidate zeroes.

The evaluator is condition-blind and uses the same mixed scoring path for with-skill
and no-skill submissions. It evaluates the supplied workbook and letter against the
issued project records. Equivalent professional wording, document arrangement, and
common date notation are accepted; resemblance to Golden is not a criterion.

## Strict Score

`strict = 0.60 × numeric_score + 0.40 × semantic_score`

The strict score separates claim-value correctness from professional workflow quality.
Numeric controls receive 60% because incorrect quantities, rates, deductions, or balances
directly misstate the payment request. Semantic controls receive 40% because authority,
handoff, and evidence defects can block review even when arithmetic is correct. Each
local defect reduces only its owning weighted criterion; it does not erase unrelated
correct work. There is no exponent, hidden cap, model condition, or Golden exception.

### Numeric Component

The following weights sum to 1 within `numeric_score`:

- **Eligible lines (0.25):** correct effective line set, current quantities, rates,
  and categories. This is largest because claiming an ineligible or unsupported item
  directly changes entitlement.
- **Line arithmetic (0.10):** each submitted amount equals quantity multiplied by rate.
- **Current rollup (0.10):** submitted lines roll into categories exactly once.
- **Advances (0.15):** engineering and material additions/recoveries use the correct
  basis and engineering recovery does not exceed the remaining advance. Advances have
  elevated weight because confusing additions with recoveries creates immediate cash
  exposure distinct from earned work.
- **Retention and other deductions (0.10):** retention uses earned work and other
  deductions use their issued voucher.
- **Cumulative ledger (0.10):** opening balances follow the confirmed ledger and each
  closing balance equals opening plus current movement.
- **Summary arithmetic (0.10):** additions, deductions, and net payment reconcile.
- **Letter and supporting balances (0.10):** the letter adopts the workbook's current
  net amount, and duplicated schedule balances reconcile to the candidate's own
  summary. Within this group, the authorization-facing letter/workbook adopted amount
  carries 70%; the nine supporting balance reconciliations share 30%. The adopted
  amount therefore receives clear priority, while a local supporting-schedule
  discrepancy cannot erase unrelated correct controls.

An upstream error is scored by its owning control and is not charged again merely
because it propagates mechanically through a downstream formula.

### Semantic Component

The following weights sum to 1 within `semantic_score`:

- **Submission readiness (0.10):** project, contract, period, cutoff, addressee,
  review request, attachments, and unexecuted authorization status.
- **Q08 cutoff handoff (0.08):** post-cutoff endorsement, current exclusion, retained
  cumulative quantity, later-period routing, and accountable owner. When timing,
  exclusion, routing, and ownership are all established but the accepted cumulative
  quantity is not explicitly restated, this control receives 0.90; missing ownership
  remains at most 0.75 because no one is accountable for the transfer.
- **V03 price handoff (0.08):** supported quantity retained, proposed rate excluded,
  formal rate confirmation required, and accountable owner.
- **D02 quantity handoff (0.08):** unendorsed quantity excluded, missing authority and
  next action identified, and accountable owner.
- **Measurement revision control (0.10):** 计05-05B is operative, 计05-05A is archived,
  and Q03's signed negative measurement remains work-value evidence.
- **Price authority control (0.12):** contract, variation, and daywork lines remain
  inspectably bound to their applicable confirmed pricing authority and the supplied
  tax-and-fee-inclusive basis; no fixed phrase such as `all-in` is required.
- **Engineering advance bridge (0.11):** issued amount, prior recovery, opening
  outstanding balance, capped current recovery, closing balance, and stock identity.
- **Material advance bridge (0.13):** opening, new, recovered, and closing material
  advance remain separate, with recovery bound to the original prepaid batch basis.
  This is the largest semantic control because using a replacement purchase price can
  misstate both current recovery and the remaining financed stock.
- **Retention and debit basis (0.10):** retention uses current earned work including
  signed credits, while the separate debit is tied to its issued voucher and not doubled.
- **Attachment and adoption control (0.10):** operative quantity/price/funding records
  can be assembled, superseded evidence is distinguished, and the letter adopts the
  submitted current application rather than a cumulative, approved, or paid amount.

The three handoffs are separate because each has a different missing authority and
future action. Role responsibility is judged from meaning and context: `计量员`,
`计量工程师`, or another professionally suitable owner is valid when the action is
actually assigned. A title merely mentioned without responsibility is not.

The semantic judge must cite exact candidate evidence. Missing judge service, invalid
responses, and replay misses are infrastructure errors and do not become candidate
scores.

## Lenient Score

The binary lenient score is 1 only when the package is usable for submission: required
files parse; eligible lines, line arithmetic, current rollups, advances, deductions,
cumulative balances, and summary arithmetic are correct; the letter adopts the
workbook net amount; and all ten semantic controls are complete. A local discrepancy
in a duplicated supporting balance can reduce strict quality without failing lenient
when the core application and adopted amount remain correct.
