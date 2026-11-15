# Project Display-Test Equipment Operating Basis

## Purpose and authority

This document is a sanitized operating extract from the project's approved internal SOP. It describes the available test-chain roles and reusable operating controls. It deliberately omits the project's test-item catalog, case identifiers, case-to-procedure mapping, acceptance values, expected results, and report examples.

The project SOP, rather than the supplied R&S SMW200A manufacturer guide, is the authority for the project display-test workflow. Similar equipment names must not be treated as interchangeable.

## Equipment roles

- The project test chain includes an HDMI 2.1 signal source capable of supplying the HDR formats needed by the approved test plan.
- The project uses an SNW200A all-in-one display tester with brightness-meter, colorimeter, and oscilloscope functions.
- A brightness-meter or colorimeter probe may be positioned at the prescribed screen measurement location and must be calibrated before measurement.
- The project control software exposes connection status and measurement or recording functions used by the approved procedure.
- The exact routing between the signal source, display tester, probe, and television must be verified from the installed test-chain configuration before a measurement-dependent test is accepted.

## Reusable operating sequence

1. Verify the HDMI path, selected television input, cable suitability, and source-to-display connection.
2. Power and warm the test equipment and television according to the approved preparation requirements.
3. Calibrate or zero the applicable optical probe and confirm that the control software reports the required devices as connected.
4. Configure the signal source for the required HDR format, timing, bit depth, metadata, and test pattern supported by the selected test objective.
5. Configure the display tester for the required observation, brightness measurement, color measurement, high-frequency sampling, or time-based recording operation.
6. Apply the stimulus, confirm the intended television mode or signal state, and perform the planned observation or measurement.
7. Record source settings, television settings, measurement conditions, readings, transition timing, visible artifacts, and any signal-chain exception needed to interpret the result.

## Control rules

- Do not infer SNW200A interfaces, commands, or capabilities from the R&S SMW200A guide.
- Do not assign one instrument every role merely because the project workflow uses several components together.
- A measurement-dependent result is invalid when the signal path, probe calibration, or software connection has not been verified.
- Use only the acceptance relationship supplied by the project's final approved requirements; do not recover superseded values from historical SOP versions.
- When a requested setting is not established by the supplied evidence, state the required function or controlled condition without inventing a button name, port label, sampling value, software command, or instrument feature.
