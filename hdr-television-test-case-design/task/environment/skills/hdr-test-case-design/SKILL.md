---
name: hdr-test-case-design
description: Design device-specific HDR test cases by reconciling product capabilities, HDR specifications, acceptance requirements, and test-instrument documentation. Use when a test plan must join these evidence types without treating general features as device support or confusing similarly named equipment.
---

# HDR Test Case Design Method

## When to Use

Use this method when preparing an HDR function test plan from a device specification, an HDR technology document, project acceptance requirements, and test-equipment documentation. It is intended for test design, not for reporting measurements from a test that has already been executed.

## How to Use

Before drafting, read [references/evidence-mapping.md](references/evidence-mapping.md) and [references/test-selection.md](references/test-selection.md). Use [references/test-case-review-checklist.md](references/test-case-review-checklist.md) for the final review.

### 1. Separate the evidence roles

Build three short working lists before drafting test cases:

- **Device capability:** functions and interfaces explicitly supported by the device under test.
- **Functional requirement:** the HDR behavior, signal property, or display characteristic that a test is intended to examine.
- **Acceptance requirement:** the project-approved limit, comparison, or pass/fail rule.
- **Instrument capability:** operations the available equipment can actually perform, including supported inputs or outputs, configuration controls, and measurable quantities.

Do not transfer a general HDR feature into the device test plan unless the device material supports it. Do not treat a product claim as an acceptance threshold. Do not prescribe an instrument action merely because the functional specification says that the behavior should be tested.

Before combining equipment evidence, verify the exact manufacturer, model identifier, interfaces, and documented role of each device. Similar model names are not interchangeable. When a project procedure and a manufacturer manual refer to different equipment, use each only for the claims it actually supports.

Create a private traceability ledger before drafting. Give each explicitly named device HDR capability and each row in the project acceptance table its own ledger entry. For every entry, record the supporting source, the stimulus, the observation or measurement, and the acceptance decision. This ledger is working analysis only; do not copy it into the final workbook.

### 2. Apply the three-way applicability check

A proposed test case is executable only when all three questions have defensible answers:

1. Does the device support the target function?
2. Does the functional material define a behavior worth testing?
3. Can the stated equipment chain generate the required stimulus and observe the required response?

If one side of this intersection is missing, narrow the test objective, use a supported observation method, or mark the idea as unsupported rather than inventing an operation.

Treat project acceptance relationships as coverage obligations, not as optional examples. A relationship is not closed merely because its number appears somewhere: the HDR format, operating condition, measurement quantity, boundary, and decision direction must stay connected.

### 3. Define one observable objective per test case

Write the Test Case Name so that it identifies one primary behavior. Split cases that require materially different signal formats, configurations, measurements, or acceptance decisions. Combine steps only when they belong to the same controlled comparison.

Preserve the device maker's named HDR functions in module and case names. Do not silently replace a branded capability with the underlying base format when the distinction affects the test objective.

Prioritize cases in this order:

1. device-supported HDR functions that have a project acceptance relationship;
2. device-supported HDR functions whose characteristic behavior is defined by the supplied technical material;
3. a small number of diagnostics needed to validate the signal or measurement chain.

Do not expand the deliverable into a whole-device regression plan. A useful test from a general guide is still out of scope when it does not close a device-supported HDR objective or a supplied acceptance relationship.

### 4. Make Preconditions operational

Include only conditions required before the formal test begins, such as the relevant connection, environment, device state, picture mode, signal availability, or equipment readiness. Avoid generic preconditions that do not affect the test.

### 5. Build a reproducible measurement chain

Arrange Test Steps as a complete chain:

1. establish the physical connection and power state;
2. confirm that the device and equipment are ready;
3. configure the required signal, format, mode, or test pattern;
4. apply the stimulus to the device under test;
5. observe or measure the intended response;
6. record or compare the result needed for the acceptance decision.

Keep setup actions separate from formal test actions. Preserve dependencies between steps so that another tester can reproduce the procedure without guessing an omitted transition.

### 6. Write Expected Results from the measurement chain

Each Expected Result must answer what should be observed or measured after the corresponding steps. Tie every result to the same function, signal, and comparison used in the test. Use a numeric limit only when it is supported by an acceptance requirement or other authoritative material; otherwise state an objective observable or comparative condition without inventing a threshold.

### 7. Perform a closure review

Before delivery, verify each row in both directions:

- Every step contributes to an expected result.
- Every expected result is produced by at least one step.
- The Test Module agrees with the device-supported function.
- Preconditions are sufficient but do not claim unsupported equipment functions.
- Repeated setup language has not hidden a case-specific omission.
- Every ledger entry has been closed by at least one submitted case, even when one case was split across several rows or several related checks were consolidated.
- Every submitted case traces back to a device capability, a project acceptance relationship, or a necessary signal-chain diagnostic.

Deliver the final test item list in clear English and preserve a consistent spreadsheet structure across all cases.

After creating the workbook, run:

```bash
python /app/environment/skills/hdr-test-case-design/scripts/check_deliverable.py <workbook-path>
```

The checker validates only workbook readability, required fields, and structural completeness. It does not contain test answers or score professional correctness.
