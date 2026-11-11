---
name: effective-period-allocation
description: Allocate expenses and reconcile balances across changing owners or departments using stable identifiers and effective periods in spreadsheet models.
---

# Effective-period allocation

Separate the identity of an item from its position in a worksheet. Determine
the grain of each source: one asset, one event, one month or one closing balance.
Use stable business keys to connect those grains.

Read [keyed events](references/keyed-events.md) when implementing ownership
changes, and [stocks and flows](references/stocks-and-flows.md) when connecting
monthly expenses to closing balances and departmental summaries.

Resolve the applicable owner for each period before aggregating amounts.
Preserve both the event history and the reporting cutoff. A current owner alone
cannot identify where an earlier month's expense belongs.

Validate conservation over the complete supported population and inspect at
least one item across an ownership boundary. Keep the workbook's stated
effective-date and opening-state conventions explicit rather than inventing
business events to make grouped totals agree.

