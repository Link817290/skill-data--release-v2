---
name: scope-repair-enquiries
description: Turn existing building work schedules into a scoped repair enquiry, preserving measurement bases, bundled construction details and unresolved quantities.
---

# Scope repair enquiries

Use this when an existing bill covers a wider refurbishment than the requested enquiry. The output should let contractors price the same scope; it is not a substitute for a survey or a signed works contract.

Start with the requested physical boundary and the source bill's building, location, work stage, unit and item identifier. A matching material name is insufficient: removing a finish, replacing it and transporting the waste have different quantity bases. Keep each source item identifiable even if the presentation changes.

- For selecting or splitting work, read [scope-boundaries.md](references/scope-boundaries.md).
- For multilayer systems, accessories and composite rates, read [bundled-items.md](references/bundled-items.md).
- For uncertain quantities and quotation readiness, read [quotation-closure.md](references/quotation-closure.md).

Recompute subtotals by compatible work stage and unit. Use [quantity_groups.py](scripts/quantity_groups.py) on a normalized working CSV when useful. It separates known totals from unresolved records and refuses mixed-unit groups. It cannot decide which works belong to the enquiry.

Before delivery, read the scope note against the actual priced-bill fields: a provisional quantity must not become an approved quantity in prose; a retained unknown must not silently become zero; an included layer must not disappear from contractor obligations. Test an alternative plausible interpretation of each broad item before accepting it.
