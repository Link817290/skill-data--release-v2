# Causal tests and measurement definitions

## Several routes can produce the same visible action

List the routes that could cause a response and design a control that disables each
competing route while preserving the route under test. Verify the disabled state;
requesting a disconnect is weaker evidence than observing the link or a route-specific
function disappear. Repeat the same command with the selected path obstructed and
restored. If the action continues, investigate another cause before attributing it.

An external device may respond through learned optical control, a host-side control bus
or another wireless controller. Demonstrating one visible action does not establish
learning. Compare the unlearned reference condition, learned state and path-blocked state; keep
other routes inactive during the comparison. Test persistence by retesting the stored
mapping after the applicable reset, before manually recreating it.

Verify what the reset actually removes. Disconnecting a charger while a battery
continues to supply the device does not interrupt device power. Cycling a host does
not establish persistence in a controller's own storage. Name the state or storage
owner, the supported reset operation, evidence that the reset occurred, and the first
observation after restoration. Repairing a connection or recreating a mapping before
that observation destroys the retention comparison.

For several targets, observe the intended and unintended targets during the same input.
Distinguish addressed traffic from a shared broadcast path. Record a reference condition, the
stress condition and recovery while holding unrelated variables fixed. An unresponsive unintended receiver
screen that nobody observed does not support a no-cross-control conclusion.

## Rates and latency

Define each numerator and denominator before writing a threshold. Retain failed and
timed-out attempts in the intended attempt population. Recognition, intent correctness
and executed-action correctness are distinct outcomes. Word-level error metrics use a
word population and must not be relabelled as command success.

Make a trial record before selecting rate thresholds: reference input, received or
recognized content, intended operation, observed operation, failure or timeout, and
condition. Derive recognition and action counts from their own columns. A rule that
calls recognition correct only when the action also succeeds silently makes a joint
metric, even if the report later labels the measures separately. State which population
each rate covers and how a non-response remains in it.

For a comparison under noise or another environmental stress, use an identical utterance set and
control speaking geometry, input level, device state and service conditions. Measure
the stress at the relevant observation point; a user-interface volume percentage does
not measure acoustic pressure. Report absolute rates, differences between rates on the same percentage scale and
relative changes separately. A relative loss from a zero reference condition is undefined.
Locate the stress measurement itself: the speaker's distance from a microphone does
not specify where a sound-level meter samples the noise field.

Name both timing endpoints. User-interface appearance, connection establishment,
recognition completion and actual action can occur at different times. Record repeated
observations before reporting a mean, and retain exceptional outcomes. Match instrument
resolution to the quantity; a coarse timer cannot establish a fine latency claim.

## Geometry and state

Change distance while holding angle and receiver orientation fixed, then change angle
at a fixed distance. Record counts per geometry point and verify which route carried
the command. A specified design distance does not imply perfect reception at every orientation.

For short and long presses or app-dependent controls, restore the same starting state,
measure the input duration and record the resulting state or navigation depth. Do not
treat a missing app feature as a device fault until support is established.

A shared starting state must restore the variable being compared. Returning to a
dashboard does not restore a list's scroll position or a player's playback point.
For each branch name the relevant screen, focused item, content position and mode;
reuse a common setup only when it establishes those states for that experiment.

Stop a causal claim when the control fails, the disabled state cannot be verified or
the compared populations differ. Record what the experiment actually demonstrated and
the next test that would separate the remaining explanations.
