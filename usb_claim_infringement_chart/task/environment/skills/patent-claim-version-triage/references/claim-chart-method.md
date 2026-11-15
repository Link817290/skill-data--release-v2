---
name: evidence-led-claim-comparison
description: Compare normalized patent limitations with technical product records while preserving actor, signaling path, event order, product identity, source scope, and unresolved evidence. Use after the controlling claim text has been frozen and before assigning claim-level outcomes.
---

# Evidence-led claim comparison

## When this method applies

Use this skill for element-by-element patent analysis against product manuals,
controller datasheets, protocol specifications, test records, source code, or
other implementation evidence. Start only after a version-control pass has fixed
the exact claim text and dependency tree. If a packet contains more than one
claim version, use the version-control skill first.

This method answers an evidence question: what does the supplied record establish
for the identified target and operating mode? It does not decide validity,
enforceability, damages, or a legal doctrine that the requester excluded.

## Open the working artifact before deep review

When the deliverable contains several matrices or registers, create a parseable
artifact at the required path as soon as the axes and schemas are known. Use a
small generator or working data structure, populate one collection at a time, and
reopen the saved JSON after each collection closes. This prevents a long evidence
review from ending with no usable artifact because serialization was deferred.

An early artifact is not a license to invent conclusions. Use the output
contract's unresolved state for open judgments, then revise only after the
relevant evidence pass. Generate repeated row structure from declared axes while
keeping the analyst's substantive ledger as the source of each classification.

## Build an evidence ledger before making calls

Create one ledger entry for each supplied document. Record the document's own
identity, the target or class of targets it actually describes, its date or
revision if shown, and the smallest usable locator. Then give the entry an
evidence scope:

- An implementation record can establish behavior of the named implementation.
- A component datasheet can establish the component's behavior, but not that an
  unidentified finished product contains or enables that component.
- A reference design describes the reference build, not every commercial product
  that supports the same protocol.
- A protocol document describes compliant behavior. It becomes product evidence
  only when the record reliably ties the exact product and mode to that protocol.
- Marketing material can establish what it actually states, such as model identity
  or rated outputs. It rarely establishes internal states, firmware branches, or
  signal timing.
- A patent example describes the example. It is not evidence that a commercial
  target implements the example.

Do not flatten these scopes into one undifferentiated pile. Two documents can be
combined only after writing the bridge between them. For example, product
literature plus a mandatory protocol rule may support a composite inference if
the product is unambiguously tied to that protocol and the feature is mandatory,
not optional. Record both premises and label the bridge as an inference.

### Search long PDFs without losing page control

For long patent and protocol PDFs, avoid streaming the entire conversion through
the working transcript. Convert to a temporary text file and search it by stable
claim phrases, section labels, or distinctive terminology, or use `pdftotext`
page bounds to extract a narrow interval. Re-open the relevant PDF pages after a
text hit because printed page labels and PDF page indexes may differ. Record the
locator convention once and use it consistently throughout the chart.

Search hits are navigation aids, not evidence by themselves. Read enough adjacent
text to capture qualifications, tables, mode restrictions, and whether a rule is
mandatory. Keep source identity and local page or section with every excerpt so
later synthesis cannot detach language from its document scope.

## Normalize limitations without erasing constraints

Split the controlling claim into units that can independently succeed or fail.
Keep these dimensions separate whenever the words support it:

- structure or component;
- actor and direction of an act;
- physical path, conductor, channel, or interface;
- trigger and response;
- ordering or bounded time interval;
- content of communicated information;
- target identity, variant, and operating mode.

A preposition or temporal phrase may carry the point of novelty. Phrases such as
"from", "to", "after", "until", "during", and "in response to" should survive
normalization. A row that merely says "communication occurs" is too broad when
the claim identifies who sends what, on which path, and between which events.

For a dependent claim, materialize the complete inherited set. Do not analyze only
the final clause. Multi-level dependencies are transitive: walk the chain until an
independent claim is reached, and keep a record of every inherited source.

## Test the actor and direction

For every communication act, write four facts before judging it:

1. the sender;
2. the receiver;
3. the object sent or received;
4. the act that follows, if the claim states a response.

Commands and capability information are not interchangeable. A sink requesting a
voltage is not, without more, a source communicating all voltages it can supply.
A controller changing an output in response to a request is not automatically a
separate outbound data message. Authentication, identification, negotiation, and
control may occur in one protocol but remain different claimed content.

When a source uses passive language, do not guess the actor. Preserve the gap or
find another supplied passage that assigns direction.

## Test the physical medium

Names such as "USB", "wireless", or "network" describe a system, not a signal
path. Bind the evidence to the recited path:

- distinguish legacy data conductors from a configuration channel;
- distinguish the power rail from a data-bearing conductor;
- distinguish a physical short from two lines merely having equal voltage;
- distinguish in-band packets from an out-of-band controller interface;
- distinguish connector capability from the pins used in the relevant mode.

An open-ended apparatus may contain extra conductors, but the claimed conductors
still need evidence. Conversely, a target-specific source that assigns the same
function to a mutually exclusive channel can support a negative finding. A generic
standard that the target is not linked to cannot.

## Test event order as a partial order

Convert temporal prose into events and arrows. Useful events include attachment,
initial classification, release of a switch, request, response data, enablement,
and normal operation. Then test every claimed relation separately.

Co-occurrence is not sequence. "After connection" does not establish "after the
handshake"; a negotiation followed by a voltage change does not establish a data
exchange bounded before normal operation. If a claim defines an interval with two
boundaries, evidence for only one boundary leaves the interval open.

Do not assume the claim drafter's phase labels equal a protocol document's phase
labels. State the proposed mapping and the sentence that supports it. If the
mapping requires waveform timing or firmware state transitions absent from the
packet, preserve that as missing proof.

## Separate four evidentiary states in the working notes

Keep these concepts distinct even if the requested output uses different labels:

- explicit affirmative disclosure;
- a necessary composite inference whose premises are all in the packet;
- silence or insufficient target linkage;
- a reliable description of a mutually exclusive mechanism.

Only the first two can support presence, and the second needs its bridge exposed.
Silence does not establish absence. A different mechanism supports absence only
when the source is target-specific enough and the mechanisms cannot coexist in
the relevant mode.

Avoid "inherency" shortcuts. A protocol name, logo, power rating, connector type,
or list of voltages does not by itself establish every optional negotiation step,
message content, channel, or ordering rule associated with that ecosystem.

## Close each claim from its elements

Make the claim-level result a function of the element findings, not a separate
intuition. The favorable technical result is available only when every required
unit is supported for one target and one coherent operating mode. A demonstrated
incompatibility can dispose of the claim. An open evidentiary unit keeps the claim
open rather than becoming a negative fact.

Do not average limitations and do not combine mutually exclusive modes. A feature
from one port, a timing rule from another firmware mode, and a voltage rating from
a third product cannot be assembled into a single accused configuration.

## Evidence binding and review discipline

Every element row should point to the smallest local source key that supports the
finding. The explanation should state the bridge, not repeat the label. Before
closing a target, ask:

- Is the cited record actually about this exact target or only a class?
- Did I preserve the sender and receiver?
- Did I identify the conductor or channel?
- Did I prove both temporal boundaries?
- Did I turn advertised capability into implementation fact?
- Did I combine facts from incompatible ports, variants, or modes?

## Failure modes and stop conditions

Stop and preserve uncertainty when product identity, port, firmware, or operating
mode cannot be fixed. Stop when the necessary bridge would require an external
datasheet, teardown, waveform, source code, or protocol rule that is not supplied.
Name the missing record narrowly; "more evidence needed" is not useful.

Do not repair a sparse packet by browsing when the task limits sources. Do not
promote polished prose over the element ledger. If a claim-level result conflicts
with any element row, fix the result or the row before delivery.
