# Evidence Mapping for HDR Test Design

Use each source only for the claim type it can support.

## Evidence roles

| Source role | Supports | Does not establish by itself |
| --- | --- | --- |
| Device specification | Supported formats, interfaces, modes, and product capabilities | Test-equipment commands or universal acceptance thresholds |
| HDR functional specification | Signal behavior, metadata model, transfer function, color or luminance concepts, and relevant test intent | That the device implements every described feature |
| Instrument documentation | Connections, startup, supported signal generation, configuration, control, and measurement operations | That a test is applicable to the device or that a result is acceptable |
| Test policy or acceptance specification, when present | Numeric limits, tolerance, required comparisons, and pass/fail rules | Device or instrument capabilities not stated elsewhere |

## Three-way evidence join

For every proposed case, keep a short private ledger containing:

1. the device-supported function;
2. the behavior to test;
3. the instrument action or observation method;
4. the expected observable or measurable result.

Do not merge claims merely because they share words such as HDR, color, brightness, or metadata. The function, signal format, operating mode, and measured quantity must refer to the same test relationship.

## Missing or conflicting evidence

- Prefer a narrower executable test over an unsupported detailed procedure.
- Do not convert a product marketing statement into a measurement threshold.
- Do not infer an instrument command from a generic HDR description.
- Verify exact equipment identities before joining claims. A procedure for one model does not establish the ports, software modules, probes, or commands of a similarly named model.
- When a project acceptance document and a manufacturer manual cover different parts of the test chain, keep those roles separate instead of forcing them into one device description.
- When two materials use different terminology, preserve the technically meaningful distinction and use the term appropriate to the device or instrument.
- When a numeric acceptance threshold is unavailable, write an objective observation or controlled comparison only if the test can still produce a reviewable result.
