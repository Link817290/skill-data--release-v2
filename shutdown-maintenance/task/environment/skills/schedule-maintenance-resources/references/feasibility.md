# Feasibility before priority

For each package record scope, duration basis, earliest start, allowable windows,
predecessors, required crew and equipment. Reserve crew and tool independently;
different teams cannot share a single test rig at the same time. Readiness dates
are release constraints, not evidence of completed goods receipt.

Validate proposed schedules independently from the construction algorithm:
coverage, duration, windows, each resource's interval collisions and precedence.
Then compare only feasible alternatives under the business's explicit priorities.
If priorities are ordered, solve sequentially or enumerate the feasible set with
lexicographic comparison. A weighted sum can sacrifice a higher priority silently.

A reference schedule is one witness. Equivalent schedules that meet the same
constraints and priorities remain valid. To claim earliest completion, retain a
lower bound or an exhaustive/solver certificate under stated assumptions. If an
estimate changes, that certificate no longer proves the operational result.

Check the exported workbook, not just the internal plan: date types, inclusive
end dates, daily marks and follow-up rows must agree. A shifted table with an old
Gantt picture is a real handoff defect.

Make a standalone calendar interpretable: include the year and identify closed
windows or shading meanings. Check printed long notes for clipping as well as
checking that their complete text exists in cells.
