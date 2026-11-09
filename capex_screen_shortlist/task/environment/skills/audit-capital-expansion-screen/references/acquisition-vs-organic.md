# Organic vs Acquisition-Driven Expansion

The auxiliary indicator goodwill / net assets is a *reading aid* for growth-sector
companies, not a gate. Its job is to tell you whether a company that clears the
expansion test grew organically or by acquisition.

## The trajectory is the tell, not the level

Goodwill arises only from business combinations and is only reduced by impairment.
So the signal is the change in goodwill across the window (2019–2021), read year
by year — not the size of the balance.

- A goodwill balance that rises in a window year points to an acquisition *in
  that year*.
- A goodwill balance that is large but flat across the window is a *historical*
  acquisition (pre-window). For this window the company is ORGANIC — a big level
  is not, by itself, acquisition-driven expansion.
- Impairment can hide an acquisition: a purchase and a write-down in the same
  year can net to a flat or lower balance. A year-over-year increase *net of
  impairment* still means an acquisition that year. The structured mirror carries
  the year-end goodwill balance only, so a purchase that a same-year write-down
  nets flat is not separable from it — that is a limit on what the balances can
  show, not evidence that no combination happened.

## Dating the combination

Date the combination from the year-by-year goodwill balances across the window:

- A balance that rises in a window year → window acquisition signal →
  `ACQUISITION_DRIVEN`, dated to the year the rise appears. This is the
  balance-trajectory classification; retain `REVIEW` for a stronger causal
  claim when no binding transaction filing was supplied.
- A balance already in place at the window's first year and merely carried forward
  → **not** window-driven → `ORGANIC` for this window.

Boundary cases — a change small enough, or a trajectory ambiguous enough, that the
balances cannot date the combination — are missing evidence, not a close call to be
resolved by judgment. Hold the cell at `REVIEW` under the three-state discipline and
say which year could not be dated. Cite the source id and fiscal year of each
goodwill balance you read.

## What to report

For each company: the classification, the goodwill balance by year with its source
id, which window years show a combination-driven increase, and — when
`ACQUISITION_DRIVEN` — the year and the size of the increase that carries the call.
