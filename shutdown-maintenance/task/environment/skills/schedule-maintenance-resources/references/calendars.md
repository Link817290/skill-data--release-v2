# Calendar semantics

Keep four concepts separate: working shifts, elapsed process time, availability
windows and due-date rules. A weekend may stop site work while continuous standby
continues. A month is not necessarily thirty days. Define whether duration counts
both start and finish dates and whether work may pause across a closed window.

Represent each resource interval consistently, preferably half-open [start,end).
Normal overnight handover does not automatically authorize pausing a package for
several closed days. Read the planning conditions instead of compressing a calendar
into unnamed slot numbers and losing the gap.

Attach deadlines to events: completion, energization, delivery or actual restart.
When an upstream date moves, recompute all dependent dates, including follow-up
outside the visible outage chart. Do not force a later inspection into an earlier
standby window just to make the chart end neatly.
