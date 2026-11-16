---
name: prepare-progress-payment-applications
description: Prepare construction progress-payment applications from measurement records, contract pricing, variations and advance ledgers. Use for compiling claim schedules and submission letters; do not infer payment approval from a calculation.
---

# Prepare a progress-payment application

Build the claim the project team can submit. Keep the supporting chain inspectable from an application line back to a measured quantity, a price authority and a payment term.

1. Establish the contract, period, cutoff and receiving institution from the routing documents. Separate measurement completion from the date its required endorsement became available.
2. Build a document register before calculating. Track item identity, cumulative/current basis, revision status, quantity endorsement and price endorsement independently. Use [eligibility and revisions](references/eligibility.md).
3. Assemble eligible quantities and prices, keeping signed negative adjustments. Calculate line amounts before category subtotals. Use [pricing and rounding](references/pricing.md).
4. Bridge each advance stock separately; calculate retention against its defined basis. Use [cash-flow components](references/cash-flow.md). The optional [calculation helper](scripts/payment_components.py) handles decimal line rounding and a capped recovery after you have established the business inputs.
5. Complete the requested application form and its supporting schedules. Transfer only source-supported opening amounts. Use [submission assembly](references/submission.md).
6. Independently check the claim, the amounts in the letter and pending-item routing. Use [validation cases](references/validation.md).

Preserve the requested field labels and file destinations. Row order and visual arrangement can change without changing the business meaning. A source ambiguity may justify holding an affected line; it does not justify omitting the rest of a valid claim or substituting an audit report for the requested application.
