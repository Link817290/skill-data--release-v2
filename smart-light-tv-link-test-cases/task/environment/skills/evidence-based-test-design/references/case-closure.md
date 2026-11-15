# Closing a Test Case

Review the saved case as instructions for an engineer who has the supplied
equipment but has not read your working notes. The following distinctions
often determine whether a plausible case can actually be executed.

## Effective starting state

Inventory names identify equipment, not state. Write how to establish a valid
configuration: topology, enrolled devices, active feature, selected operating
branch, firmware compatibility, background stimulus and relevant environmental
conditions. When setup is inherited, identify the setup case and any overrides.
The inherited state must still hold at the time of the trigger.

For a transition between modes, start in the original mode and then change it.
For loss and recovery, first prove normal operation, introduce the fault at the
named link, keep a stimulus running, observe the failure behavior, remove the
fault and repeat the original behavior. Loss at a device, controller, local
network and upstream service are different injections. Choose the one claimed
by the case. For degraded service, define a controlled degradation profile and
verify that it was actually applied; an outage does not measure degraded service.

Conditional features need an executable branch with the documented capability
enabled. If that capability is unavailable, record blocked execution with the
missing evidence. Do not replace the entire test with a request for clarification.

## Functional observation and quantitative verdict

Do not stop at "observe normal behavior" or "measure response using case X."
Describe the expected effect at the actual endpoint: which device changes,
which property changes and how that change follows the controlled stimulus.
Then add the measurement contract. Both belong to the scenario, even when
the detailed instrumentation is shared.

For a synthetic actuator example, "send the command and read success" measures
transport. To test the output, establish the actuator's initial state, issue
the command while recording, detect the specified physical change, pair that
event with the source-defined trigger and calculate the interval. State the
instrument and detection rule rather than inventing a specification threshold.

For multiple quantities, label separate clauses. An interval and a percentage
do not share a threshold. A local response and an external response do not share
an endpoint. Repeat the applicable source binding beside each verdict. Clearly
distinguish adopted requirements, unresolved alternatives and exploratory
observations; uncertainty should change the verdict, not erase the procedure.

For concurrent devices, retain device identities and separate results. Show
the limiting device or required aggregate without averaging away a failure.
For relative changes, capture comparable baseline and final states at the same
measurement plane. Where a baseline is unresolved, define how to acquire it and
which relative verdict remains conditional.

## Coverage without case proliferation

Use the requested scope as the coverage boundary. A small number of complete
cases is more useful than many rows split into setup-only, action-only and
expectation-only fragments. Share stable fixtures and methods through explicit
references; preserve distinct stimuli and outcomes in each scenario's row.

Check interactions as state transitions, not an unrelated feature checklist:
entry, steady operation, changes while active, failure and restoration where
the supplied requirements call for them. Include documented notifications at
their actual endpoint even if another interface is excluded from scope.

Explain priority using failure impact, reach and recoverability. Equipment
lists must include instruments and access that the methods actually require.
Do not mark a planned case passed merely because its design is complete.
