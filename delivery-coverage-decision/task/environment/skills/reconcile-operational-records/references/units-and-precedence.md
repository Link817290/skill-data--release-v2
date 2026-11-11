# Units and document precedence

A later document may replace a scoped row, add a resource increment, or temporarily override availability. Record which operation it defines. Do not treat every later number as an additive change.

Apply changes in the order established by the business records. For example, a shutdown can apply to all installed equipment, including recently purchased additions. Reversing shutdown and investment operations can incorrectly restore unavailable resources.

Use a unit ledger: field, displayed unit, canonical unit, conversion and rounding stage. Keep monetary conversion exact with decimal arithmetic. Human-readable prices should use the document's customary units; internal normalization is not a reason to expose awkward amounts in prose.

Keep resource dimensions separate. Processing time, order slots, refrigerated slots and travel time are not interchangeable capacities. Preserve the resource grain, such as facility by date by dispatch period, unless borrowing or carryover is explicitly allowed.

Coordinate labels and axis order are independent properties. Convert coordinates into the prescribed metric system before snapping or measuring. Apply thresholds before presentation rounding. State whether time rounding occurs per segment, per route, or after adding other components; the stages can produce different eligibility decisions.

When extracting Word tables, account for merged cells. A vertical continuation can be empty in XML while displaying its parent's value. Parse logical cells or explicitly reconstruct merge continuations; validate the reconstructed table against the rendered document.
