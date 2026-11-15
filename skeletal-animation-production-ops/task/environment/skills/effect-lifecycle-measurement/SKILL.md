---
name: effect-lifecycle-measurement
description: Measure effect instance lifetimes and combat-event cardinality, ordering and positions in an engine integration using independent observations.
---

# Effect lifecycle and event measurement

Use this skill when repeated triggers, delayed completion or gameplay notifications need investigation. It describes how to observe behavior without prescribing ownership changes or a signal implementation. Obtain each public call's meaning and each event's meaning from the caller contract before interpreting an event count.

## Define observable identities

Track requests, visual instances, motion instances and business events as distinct entities. One request can legitimately create several visuals; one visual can legitimately outlive a motion. Neither relationship should be inferred from a shared display name. Use stable engine instance identifiers or a trace identifier that survives renaming, and retain the mapping between request and observed object. A counter maintained by the candidate implementation is supporting evidence, not an independent count of scene objects.

Define the observation interval and clock. Record trigger time, first observed presence, first visible contribution, animation completion, motion arrival, removal request and actual absence separately when available. Scene-tree deletion may occur after the operation that requests it. A single snapshot therefore cannot distinguish completed removal from scheduled removal. State the sampling bound rather than silently treating adjacent engine frames as the same instant.

## Express the contract as relations

Describe event cardinality in terms of the initiating business operation: zero, one, or a specified sequence of notifications under a defined condition. Record event payloads, not merely counts. Two events at the wrong destination do not satisfy a requirement for two correct arrivals. Conversely, display callbacks and business callbacks can share a name without sharing a contract; identify the subscriber and meaning before combining traces.

Use interval and ordering relations for lifetime requirements. Examples of relation types include presence before a declared completion boundary, absence after a bounded grace interval, or distinct instance identities during an overlap interval. These are general specification forms, not instructions about where cleanup or notification logic belongs. Keep timing, independence and event meaning separable so one observation does not stand in for all three.

## Collect discriminating observations

Observe isolated calls and overlapping calls when both are allowed by the API. Choose inputs that distinguish geometry and identity, rather than repeating a single symmetric example. When the contract admits different travel directions, compare several directions in a common world coordinate system. Include a quiet period after activity to measure leftovers and late notifications. An endpoint that looks correct at one instant can conceal a later duplicate or persistent object.

Subscribe an external recorder to the public event surface and inspect the actual scene tree. Record raw observations before summarizing them into pass/fail fields. If the implementation exposes diagnostic metadata, verify that it agrees with the object type and observed behavior. Missing metadata should not automatically invalidate an otherwise supported public interface unless metadata is explicitly part of the contract.

## Interpret evidence conservatively

A duplicate event establishes an observed contract violation; it does not by itself identify which callback caused it. An object remaining in the tree establishes retained state, but visibility and interaction still require separate measurements. A disappearing sprite does not prove the underlying object was released. Keep these conclusions distinct in the incident record.

Use [trace-relations.md](references/trace-relations.md) to organize the evidence. Attach the raw trace, sampling parameters and relevant caller specification. State whether tests cover cancellation, restart, pooling or concurrency; do not imply coverage of these behaviors when only ordinary completion was observed. Implementation choices follow the measured contract and remain outside this measurement skill.
