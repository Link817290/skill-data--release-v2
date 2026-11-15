# Scoring Rubric

The evaluator measures the delivered Godot project, fresh preview exports, and
ticket handover against the supplied integration contract and original assets.
It does not score trajectory prose or require Golden wording.

## Score Form

```text
strict = sum(weight[owner] * completion[owner])
```

Each owner completion lies in `[0, 1]`. Independent observations retain their
own partial credit; there is no exponent, global retention factor, multiplicative
gate, score cap, or hidden penalty. The ten weights sum to 1.

Seven functional and integration outcomes carry 70% in total. They are the
working client build the commission requests. Preview correspondence, the
ticket handover, and receiver-side verification carry the remaining 30% because
they make that build inspectable and transferable. Equal 10% owner weights keep
one evidence defect from erasing unrelated working behavior while giving each
contracted outcome material influence.

| Owner | Business outcome | Weight |
| --- | --- | ---: |
| F01 | Original artwork, playback resources, and rates | 0.10 |
| F02 | FX-301 hit presentation at the requested anchor with correct compositing | 0.10 |
| F03 | FX-302 independent visual-only hit calls, playback, and cleanup | 0.10 |
| F04 | FX-303 visible, grounded appearance progression and lifecycle | 0.10 |
| F05 | FX-304 world-space flight heading, path, and duration | 0.10 |
| F06 | FX-304 arrival notification, impact playback, and reclamation | 0.10 |
| F07 | Usable configured integration sequence and timetable | 0.10 |
| F08 | Fresh preview correspondence and supported capture assurance | 0.10 |
| F09 | Truthful, executed, and resolvable ticket handover | 0.10 |
| F10 | Receiver-usable independent public-API verification | 0.10 |

## Functional Owners

F01 through F07 are derived from deterministic Godot execution and source-file
identity checks:

- F01 requires the 73 supplied PNG files to remain byte-identical and evaluates
  whether the contracted artwork is visibly played at the configured rates.
- F02 combines the hit anchor and compositing observations.
- F03 combines independent instances, absence of combat notification for a
  visual-only call, and lifecycle cleanup.
- F04 combines appearance progression from the contracted source frame with
  its stable ground anchor and cleanup.
- F05 averages world heading and path/duration. World heading includes ordinary
  and rotated caller bases; the same C09 observation is used by strict and
  lenient.
- F06 averages notification cardinality/timing with impact playback and cleanup.
- F07 measures the configured default stage, including both scheduled arrivals
  and final cleanup.

These owners average complementary checks. A failed heading does not erase a
correct path, and a failed notification does not erase independently observed
impact cleanup.

## Preview And Handover Owners

F08 is the arithmetic mean of four independently measured components:

1. physical preview correspondence from the actual producer output;
2. source-bound capture-model assurance;
3. independent correspondence verification; and
4. operation of a recorded public producer procedure.

The physical component is continuous. Correct samples retain credit without a
hidden `coverage == 1` pass cliff. Reproducibility, rendering assurance, and
physical correspondence remain separate claims.

F09 is the arithmetic mean of four handover dimensions: ticket-summary factual
accuracy, correspondence to actual recorded commands, resolving artifact
bindings, and accuracy of adopted factual claims. For factual claims,
`accurate=1`, `unsupported=0.5`, and `contradicted=0`, averaged by distinct
claim. One contradicted claim loses its own share and does not zero the owner.
Equivalent professional descriptions and valid relative artifact paths count.

F10 accepts either a reusable receiver procedure or retained independent
results because either can independently support receiver regression. If both
are present, the completion remains 1 rather than receiving duplicate credit.

The semantic judge must cite the delivered sources it uses. Judge transport,
protocol, or cache failure is `needs_review`, not a candidate score of zero.

## Lenient Lens

Lenient is binary coordination readiness and is independent of the strict
number. It passes only when:

- C01 through C12 are complete, including the same full C09 world-heading
  observation used by strict;
- the configured ordinary stage is usable;
- a fresh rendered delivery has substantive physical correspondence; and
- all ticket commands correspond to actual execution evidence and all cited
  artifact bindings resolve.

Lenient does not require a particular summary phrase, exact 100% sample
coverage, or a separately executable recorded producer recipe. Those remain
continuous evidence-quality contributions under F08-F10.

## Failure And Integrity Rules

A complete inventory that lacks the required runnable project receives a
measured zero. Missing judge credentials, an exact replay cache miss, unavailable
critical evidence, or a verifier infrastructure failure remains unmeasured.
Actor artifacts are inventoried before and after scoring and must remain
unchanged. The original project is copied to a private temporary directory for
execution, and provider credentials are excluded from project subprocesses.
