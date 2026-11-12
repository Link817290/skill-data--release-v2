# Compute only a well-defined comparison

## Units, denominators and censored results

Label numerator, denominator and basis before calculating. Concentration
in mg/m³ times flow in m³/h becomes kg/h after division by one million.
That identity does not prove that the two observations were simultaneous or
reported at the same wet/dry, reference temperature, pressure or oxygen basis.
Avoid pairing a corrected concentration with an incompatible uncorrected flow.

Recalculate from reported inputs and preserve the originals. A discrepancy
cannot identify which measured input or transcribed result is wrong. Give the
recalculation and ask the reporting entity to reconcile against primary records.
Do not change the measured concentration to force agreement with a printed rate.

Keep a capacity denominator unrounded until the final result. Annual capacity,
working days, shift hours and actual output must describe the same product and
period. Different working regimes may require a different denominator; a
calculator cannot resolve contradictory product labels.

Read the legend for ND, below-quantification, blank, slash and zero. An ND
reported as below a positive detection limit can be represented by [0, DL),
not by a measured zero. Detection and quantification limits are not interchangeable.
Use an approved substitution rule only for the calculation it governs, identify
it, and assess whether the decision changes across the admissible interval.
If the censoring interval straddles a limit, no definite pass/fail follows.
No listed limit means a result can be reported but requires another applicable
criterion before a compliance conclusion; it is neither zero nor infinity.

## Concentration and removal are different questions

Separate measured, reference/normalized and evaluation concentrations. Apply a
maximum, correction factor or averaging rule only if the applicable method
requires it; “always take the larger” is not universal. Check sample validity
before averaging, and distinguish an average of transformed samples from a
transformation of averages where the method requires paired data.

Removal efficiency is based on input/output pollutant mass rates. Equal flow
cannot be presumed: leakage, dilution or extraction changes can invalidate a
concentration-only ratio. Require paired event, treatment unit, pollutant,
sampling conditions and comparable reference basis. The same date, similar
labels or another analyte's daily flow do not establish pairing.

If inlet mass is zero, removal efficiency is undefined. If it is censored near
zero, a single efficiency may be unidentifiable; obtain appropriate evidence
or evaluate bounds explicitly. A negative computed efficiency is a diagnostic
flag, not something to clamp to zero. It may indicate a mismatch, variability,
measurement uncertainty or a real process issue; investigate before deciding.

## Samples and annual totals

Compare each required spatial, temporal or operating category to its own
criterion. Do not omit an already measured category merely because the narrative
mentions only one. A correct numerical comparison is distinct from campaign
validity and from completeness of the sampled sources.

An annual mass estimate needs source inventory, compatible rates or emission
factors, activity by operating mode, hours, control effectiveness and any required
unorganized/fugitive component. Integrate over modes and sources without double
counting. A short compliant campaign alone does not prove annual total compliance.
If representative activity is missing, present the required accounting inputs
or bounded scenarios rather than claiming a measured annual result.

## Calculation helper

Examples use independent generic quantities:

```text
python scripts/review_checks.py rate --concentration-mg-m3 2.4 --flow-m3-h 17500
python scripts/review_checks.py load --annual-capacity 750 --working-days 250 --actual-daily 2.7
python scripts/review_checks.py nd --detection-limit 0.08
python scripts/review_checks.py efficiency --pair-file pair.json
python scripts/review_checks.py coverage --monitoring events.csv --operating logs.csv
```

The efficiency JSON contains `inlet` and `outlet`, each with `pair_id`, `pollutant`,
`basis`, `concentration_mg_m3`, and `flow_m3_h`. IDs, pollutant and basis must
match; missing/censored values are not guessed. Matching supplied metadata
does not itself prove valid sampling, so the result remains conditional.

Coverage CSVs have `process,date` (ISO dates); monitoring also has a unique
`event_id`. Multiple events on one day remain separate. Exact process/date
joins reveal gaps but cannot prove hourly alignment, stability or log quality.
The helper rejects malformed dates and missing identities. It does not apply
legal limits, decide sample validity or estimate an annual total.
