# Controlled Device Test Planning Rubric

The scorer requires source-bound semantic judgment for test intent, causal
isolation and equivalent procedures. Keywords and headings only locate evidence;
they do not earn credit. Missing judge evidence is UNMEASURED, not zero.

## Positive completion

Applicable assertions within each owner share that owner's weight. Conditional
WER evidence is excluded when WER is explicitly unused.

| Owner | Weight |
| --- | ---: |
| P01 Shared foundational controls | 0.06 |
| P02 Pairing event definitions | 0.08 |
| P03 IR fallback causal proof | 0.06 |
| P04 Interference and non-target observation | 0.08 |
| P05 Power recovery and binding retention | 0.08 |
| P06 Pointer motion and timer separation | 0.08 |
| P07 Application and press context controls | 0.06 |
| P08 Voice latency endpoint separation | 0.08 |
| P09 Recognition and action denominators | 0.06 |
| P10 Matched acoustic experiment | 0.07 |
| P11 Learned IR versus CEC | 0.06 |
| P12 Radio geometry and nominal limits | 0.07 |
| P13 Shortcut applicability and endpoint | 0.08 |
| P14 Audio endpoints and isolated external control | 0.08 |

The weights follow causal-test consequence and dependency breadth. The 0.08
owners govern event pairing, interference isolation, recovery retention,
pointer/timer separation, voice endpoints, shortcut applicability and audio
isolation; a defect in any of these can reverse the attribution of a test
result. P10 and P12 receive 0.07 because matched acoustic comparison and radio
geometry are material quantitative controls with narrower downstream scope.
The 0.06 owners provide shared setup, fallback proof, context, denominators and
route distinctions that support the higher-weight endpoint decisions without
duplicating them. These are relative professional-risk shares, not pass
thresholds. Each owner still earns the fraction of its applicable atomic
assertions, so an isolated missing control does not erase unrelated correct
test design.

Detailed source anchors and atomic obligations live in
`task/tests/scoring_params.json`. Equivalent controlled procedures receive the
same completion when they preserve actor, initial state, action, observation,
endpoint, competing-cause control and scope.

## Damage retention

Strict reward is:

`positive completion * product(independent damage coefficients)`

Each affirmed professional damage has coefficient `0.7`: unsafe power
substitution, unsupported timing/range guarantee, invented results, wrong route
attribution, unsupported feature availability, host facts used as DUT facts,
wrong voice-clock origin, action success substituted for recognition accuracy,
wrong-device retention proof, or a functional proxy used as electrical
low-power proof.

The coefficient represents high professional damage while retaining credit for
independent correct work. Manifestations sharing one causal root are charged
once. Ordinary omission is never converted into affirmative damage; it only
reduces positive completion. There is no fixed total-score cap.

## Lenient readiness

Lenient reward is `1` only when all three readiness checks pass:

1. At least one substantive owner is complete in each named domain:
   communication, pointer, buttons, voice and universal control.
2. No affirmative route, clock-origin or measurement-object conflation is found
   (`D04`, `D07`, `D10`).
3. No invented execution result is found (`D03`).

Otherwise lenient reward is `0`. This readiness conjunction is independent of
the continuous strict settlement.

## Evidence semantics

Workbook-scoped setup declarations may support cases that explicitly reference
them. Quoted, hypothetical and rejected actions are excluded. Missing evidence
earns no completion; an adopted contradictory or causally invalid experiment is
wrong. Directed metric formulas are checked with exact bounded rational algebra,
and fixed all-N populations are valid denominators.
