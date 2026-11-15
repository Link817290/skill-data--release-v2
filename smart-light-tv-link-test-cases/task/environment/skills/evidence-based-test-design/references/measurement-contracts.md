# Measurement Contracts

Define recomputable observations before passing thresholds. Keep functional
effects, measurements and sources together or linked by explicit case references.
Specify required instruments and access.

## Events and timebase

Use source trigger t0 and response t1 in one timebase. For seconds, `t1 - t0`;
for milliseconds, `1000 * (t1 - t0)`. For recorded video annotate trigger frame
f0 and response frame f1 and use `(f1 - f0) / fps` seconds with the actual
frame rate. Define which visible event establishes the required effect.

A local effect, external actuator, transport response and notification are
different endpoints even when they share a stimulus. One endpoint's limit does
not become another endpoint's threshold. Unknown applicability is an unresolved
decision, not permission to pick a convenient limit.

Define population and statistic. For nearest-rank percentile p sort n valid
observations and select rank `ceil(p*n)` where p is a fraction. Keep missing
responses as failures or explicitly censored observations. A percentile cannot
replace a per-event ceiling. Record each concurrent device and the maximum;
do not average away the slowest actuator.

## Relative measurements

Reduction is `100 * (baseline - observed) / baseline`; growth is
`100 * (final - initial) / initial`. The source determines comparable state and
measurement plane. A maximum slider setting is not automatically the baseline.
Define how to obtain the baseline before seeing results. An unknown baseline
blocks the final relative verdict but does not remove measurement design.
Keep a separate categorical observation separate from a percentage criterion.

Identify the process/counter and compatible initial/final monitoring states.
Adopt counter limits only with approved access and applicable evidence. Do not
invent diagnostic limits; unclaimed diagnostics require no disclaimer.
For frequency/smoothness justify observation bandwidth and event detection;
subjective jumps cannot establish an unobservable frequency.

## Ledger method field

`method` contains `kind` and `expression`. The inputs below are variable names
for the checking tool, not actual equipment measurements.

| Kind | Inputs | Measurement definition |
| --- | --- | --- |
| `elapsed` | t0, t1 in seconds | end minus start, in the criterion's time unit |
| `video` | f0, f1, fps | frame difference / recording rate, in the criterion's time unit |
| `reduction` | baseline, observed | percentage decrease from baseline |
| `growth` | initial, final | percentage growth from initial |

Expressions use arithmetic and parentheses. The tool accepts algebraic
equivalence on varied synthetic inputs and detects reversed subtraction, a
wrong denominator, missing time conversion or a constant. Other methods are
valid: set `kind: other` and give `description` with observable, instrument,
sampling/aggregation and decision. The tool returns a manual-review notice.
No method dictionary is required for non-numerical criteria.
