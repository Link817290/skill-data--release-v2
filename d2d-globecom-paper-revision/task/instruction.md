Please revise the English conference paper in `materials/D2D_conf.zip` to a
submission-ready Globecom Workshop manuscript and deliver the final artifact as
`output/revised_manuscript.pdf`.

This is a precise technical revision of the existing paper, not a replacement
paper with a new notation system or an aggressively compressed rewrite. Refocus
the narrative from broad HetNet resource allocation to cooperative D2D relaying,
while preserving the same research object, network model, and supported evidence.
Do not guess or invent authors, affiliations, experimental values, or runtime
records.

Trace the original problem, continuous relaxation, theoretical argument, and
low-complexity algorithm to identify the core defect affecting the bound on the
number of active time-reuse patterns. Determine whether the old conclusion is
wrong or merely loose, and propagate the correction rigorously through the
representation, proposition, candidate set, pruning, and stopping logic. Make the
resource constraints in the formal relaxation and the algorithm consistent with
the revised assumption that an active server uses the pattern's available time,
and state explicitly the positive effective-rate domain required by the sum-log
objective. Update the abstract, contributions, and conclusion only as needed to
carry this technical chain.

Edit against the supplied draft as the baseline. Content that is not part of the
correction above or one of its direct downstream consequences should remain
unchanged. In particular, preserve the variables and their meanings, per-pattern
user association, the receive/forward-debit/effective-rate relationship, the PF
objective, candidate reporting and final association recovery, existing figures
and numerical values, authorship, and citations. Every substantive edit should
have a clear answer to: “Which necessary correction requires this change?” Do not
rewrite unrelated sections, remove unrelated content, substitute a different
optimization problem, or invent a different algorithm.

The package contains no simulation code, raw data, or new runtime records. Do not
fabricate experiments or claim that archived figures validate a materially
changed implementation. Where new evidence is required, weaken the claim or mark
it explicitly as requiring future validation. The PDF must remain a complete
conference paper whose equations, symbols, algorithm, figures, references, and
cross-references are readable.
