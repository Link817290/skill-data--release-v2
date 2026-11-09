# Measurement check

An offline Python utility for reviewing the supplied mass-comparison records and optical reference controls. It recalculates the limits from the input records and settings; it does not contain a table of expected exceptions.

## Run

Install the packages in `requirements.txt` in the Python environment. No network connection is used by the utility itself.

```sh
python /workspace/output/measurement-check/measurement_check.py --mass /workspace/input/instrument-history/mass-checks.csv --optical /workspace/input/instrument-history/optical-checks.csv --config /workspace/input/instrument-history/control-settings.json --output /workspace/output/
```

All four paths are explicit. Quote paths containing spaces. Input row and column order do not affect the result; Record IDs identify measurements. The output directory is created if necessary. A successful run writes `review-results.json` and `exceptions.csv`, replacing files with those names in the selected output directory, and prints the summary. An input error returns a nonzero exit code with a message on stderr. Run each review into a fresh directory to keep earlier results separate.

The published `measurement-interface.json` describes the CSV columns, result fields and status codes. CSV input is UTF-8, with or without a BOM. Each mass input describes a single balance, check-standard and design combination; mixed or blank system identifiers are rejected. The utility rejects duplicate or missing Record IDs, nonfinite measurements, negative residual SD, incomplete daily reference groups, invalid control parameters and an unsupported family method.

## Calculation basis

The baseline is defined by decimal year strictly below the configured cutoff. Monitoring records are excluded from that baseline; repeated decimal years remain separate runs. The sample SD uses n−1. Residual variances are pooled with their degrees of freedom before taking the square root. The upper precision limit uses the upper-tail F probability, with single-run degrees in the numerator and actual baseline degrees in the denominator. A baseline exception is retained and marked for investigation rather than silently removed.

For the optical system, the forward relation is Y=a+bX. Corrected width is `(Y-a)/b`; control error is corrected width minus reference width. The simultaneous two-sided t probability is derived from the configured Sidak family significance and group size. Residual SD is converted to the width scale using the absolute slope. Equality to either control limit is within limits. If any reference fails, the daily result requires repeat measurement of the linked workload; the tool does not turn reference-control counts into customer-work counts.

`exceptions.csv` contains one row per failing metric. A mass run failing two metrics would appear twice there but once in the summary exception count. The one-sided residual-SD check has a blank lower limit. `review-results.json` includes every received record, each observed optical day, the reconstructed baseline and the monitoring trend, so passing records remain inspectable.

## Reading the supplied records

The received mass series gives 99 baseline records and 118 monitoring records, with 297 baseline residual degrees. The legacy 117/351 entry is retained for reconciliation; the discrepancy does not establish that 18 records were lost. M047 is a historical baseline precision exception. Monitoring runs M129, M154, M179 and M207 require repeat-work review. Optical controls L010-L012 fail on day 4, so the corresponding daily result identifies that linked-work scope.

The monitoring mean lies above the baseline mean, and 97 of 118 monitoring values exceed the baseline mean. This supports review of process change even though most individual checks are within limits. It does not identify a particular failed component or justify rejecting every measurement.

## Applicability

Retaining M047 follows the fixed historical reconstruction rule; it does not certify a stable baseline for future work. Before operational reuse, reconcile that run and the legacy population, assess process stability, and obtain technical approval for the reference limits. The variance and t-based procedures also rely on suitable measurement-distribution and independence assumptions; calculating a limit does not validate those assumptions.

The optical checks exercise the supplied linear calibration at 0.76, 3.29 and 8.89 µm. They do not establish validity outside that checked range or supply missing product tolerances. The configured family significance applies to the reference group within a checking period, not to every result across the entire archive.

## Evidence limits

No complete client-work register, product tolerances, uncertainty-based acceptance data, repair history or completed remeasurement evidence accompanies these files. `affected_customer_work_count` is therefore null, `product_conformity` remains `not_determined`, and completed remeasurement is not confirmed. A later passing control does not establish that earlier work was repaired or repeated.

For retrospective use, retrieve the affected runs' work orders and result-use links, the full day-4 workload register, and any subsequent repeat and authorization records. A known linked item does not prove complete coverage of the affected group. Baseline reconciliation and M047's historical action need their own supporting records. Closure requires valid repeat results and technical authorization; this utility provides statistical checks and evidence pointers, not product release approval.
