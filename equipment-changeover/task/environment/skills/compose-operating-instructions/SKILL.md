---
name: compose-operating-instructions
description: Turn equipment manuals and planned job conditions into scoped operating instructions with actionable steps, recovery branches and genuine release conditions.
---

Write for the person executing the change, preserving the requested document form.
Use [state transitions](references/state-transitions.md) to connect setup, trial,
verification and release. Use [exceptions](references/exceptions.md) when failures
can be mistaken for acceptable workarounds. Keep completed results separate from
future checks; never pre-sign an approval or invent a successful machine trial.

The helper `scripts/check_transitions.py` detects undefined or unreachable states
in a proposed procedure graph. It cannot prove technical safety or completeness;
check the graph's actual operations against the applicable manual.
