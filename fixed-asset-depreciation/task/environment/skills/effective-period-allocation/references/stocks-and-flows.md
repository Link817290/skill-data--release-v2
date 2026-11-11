# Stocks and flows

Expense is a flow over a period. Cost and accumulated depreciation reported for
a closing owner are balances at a point in time. They can use different ownership
dimensions without contradicting each other.

For a convention that allocates expense to the owner in the month it occurs,
attach each month's amount to that month's resolved owner before summing it.
Applying the closing department to the whole year's expense retroactively moves
earlier expense and destroys the event history.

For balances that follow closing ownership, select the owner as of the reporting
cutoff, then group original cost, accumulated depreciation and carrying amount
on that basis. A monthly expense subtotal and a closing accumulated-balance
subtotal need not be equal for an individual department after a transfer.

Useful independent relations include:

- Sum of allocated expense equals source expense for the same months and items.
- Each asset-month is allocated once, subject to any explicitly modeled split.
- Closing balance totals are conserved when an asset changes department.
- A transfer changes grouped ownership without changing the asset's depreciation
  schedule unless another supported economic driver also changes.

Compare matching populations and periods. Do not compare a top-N department
display with an all-department total and interpret the difference as a missing
charge. If the interface includes an 'other' group, ensure that its membership
does not overlap the named groups.

Read formulas as dependencies: expense -> applicable period owner -> allocation
-> period aggregate. Test whether changing an effective period moves only the
affected months, while changes after the report cutoff leave the closing state
unchanged. These are business relations, not requirements for particular cell
addresses or helper-column layouts.

