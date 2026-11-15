---
name: schedule-maintenance-resources
description: Build and validate maintenance schedules with outage calendars, package dependencies, shared crews and tools, and documented operational priorities.
---

Normalize time and resource constraints before drawing a Gantt chart. Read
[calendar semantics](references/calendars.md) for workdays versus elapsed time,
and [feasibility and priorities](references/feasibility.md) for independent checking.
Use `scripts/check_intervals.py` on a normalized schedule to detect overlapping
resource reservations. It does not infer permissions, durations or dependencies.

Distinguish estimated planning durations from observed or contractual durations.
Keep work-package scope intact while aggregating tasks; a package date is not proof
that its physical tests passed or that an operator authorized restoration.
