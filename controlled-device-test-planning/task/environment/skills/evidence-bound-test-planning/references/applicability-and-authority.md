# Applicability and acceptance authority

When documents disagree, first compare the entities and conditions they describe.
Use an internal register containing source location, device or host identity, hardware,
software, market, feature, quantity, units and applicability evidence. An apparent
conflict may disappear when the entities or event endpoints are separated.

Do not choose a source merely because it is newer, more detailed or easier to use.
Use an explicitly established precedence rule if one exists. Otherwise preserve the
competing claims, identify the configuration in which each could apply and make the
acceptance decision conditional on confirming that configuration. Measurements can
remain useful even when pass/fail authority is pending.

For example, a service guide may describe a sealed rechargeable unit while another
document describes replaceable cells. Inspect identity and construction before choosing
a power-interruption procedure. Do not turn the conflicting documents into an instruction
to open a sealed unit. An approved external procedure or a pending applicability decision
is preferable to inventing a hardware conversion.

Treat a specified design range, timeout, target latency and observed completion time as different
quantities. For each one record the trigger, stop event, operating conditions and source
authority. A timeout is not automatically a completion-time requirement. A visibility
timer is not automatically the device's low-power timer.

Separate a manufacturer's supported limit from the laboratory's chosen experiment.
Extra distances, angles, repetitions and stress durations can explore behavior without
becoming new warranty claims. Where a feature depends on region, physical controls,
installation, entitlement or host support, define both the supported branch and the
documented unavailable branch.

Counterexample: applying every field from a host datasheet to its controller confuses
entities. Similarly, picking the strictest conflicting threshold is not a substitute
for applicability. The verification is an explicit chain from entity and configuration
to the chosen authority and acceptance quantity.
