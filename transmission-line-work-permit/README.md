# Transmission Line Work Permit

Prepare a Chinese preissue work permit for the supplied transmission-line job,
including source isolation, station grounding, signage, three-direction work
grounding, controlled unknowns, and safe work/closeout procedures.

The actor image uses `harbor-claude-code-aggregated:1.3`. Run
`task/solution/solve.sh <workspace>` for the Oracle and `task/tests/test.sh` for
mixed evaluation. Grounding is judged from the supplied topology: adjacent-pole
or work-pole placement and grouped or phase-split sets are accepted when all
three directions are protected and identifiers remain controlled.
