# Product Launch Import Scoring Rubric

The required output is `products.csv`. The program layer validates the published
catalog interface, selected SKU grouping and options, planned prices, staging,
and basic content structure. A source-bound LLM judge evaluates customer-facing
product identity, supported claims, measurement scope, and physical sales units.
Equivalent English copy and arbitrary valid handles are accepted.

## Strict Score

Strict is the mean release readiness of the ten product pages, multiplied by the
numeric catalog completion. Each page combines correct product identity, its
paired source-fidelity decision, and its applicable measurement/sales-unit
scope. Pages with pack variants multiply their own 1-Pack/2-Pack and applicable
measurement-owner credit; other pages use the three measurement-scope owners'
mean. Partial semantic credit therefore remains partial instead of becoming a
hidden binary gate. A local
omission therefore affects its own page, while broken catalog structure, grouping,
options, or prices proportionally reduce the catalog as a whole. There is no
global all-pages conjunction, exponent, cap, or score floor.

The numeric catalog completion uses these published shares: schema 10%, selected
SKU range 20%, product grouping 20%, option structure 20%, planned prices 15%,
draft/import staging 10%, and usable content structure 5%. Range, grouping and
options carry the largest shares because a mistake there changes which saleable
objects will be created or merges variants into the wrong product. Price and
staging are next because they control commercial exposure. Schema and content
structure remain necessary import controls but do not outweigh the catalog's
product and variant identity.

Multiplication expresses release closure: catalog rows that cannot be imported
correctly do not become release-ready merely because their prose is faithful, and
well-formed rows do not become release-ready when the corresponding customer page
misidentifies the product, invents a claim, or obscures the physical sales unit.
The arithmetic mean across ten page results keeps each page's failure local, while
the product inside a page prevents one strong page attribute from compensating for
an incompatible attribute on that same page. This is a professional dependency
model for import readiness, not a pass threshold or a fitted score cap.

Ordinary category-consistent scene setting, such as camping, garden seating,
reading, resting, or a meal at a camping chair, is accepted as common marketing
context when it does not assert a new mechanism, supplied accessory, certified
performance, safety property, or specialized suitability. Specific capability
and performance claims still require product-card support. In particular,
duration, comfort, ease or speed of operation, comparative suitability, and
language that the product is built, ideal, or perfect for an outcome are adopted
claims rather than neutral scene-setting. Direct physical consequences that
follow from the documented construction, such as mesh permitting airflow, are
accepted without requiring identical source wording.

Claim fidelity is graded per page. A clean page receives full credit. A page
whose product identity and core physical facts remain correct but that adopts a
limited unsupported promotional benefit, duration, ease, or suitability claim
receives half credit. A direct contradiction, invented mechanism or supplied
item, safety/certification claim, or multiple material unsupported claims
receives no page credit. Each two-page claim owner is the mean of its page
scores, so local errors retain partial credit instead of zeroing an entire pair.

For pages that offer both 1-Pack and 2-Pack, an adopted product weight or load
must be scoped per chair or governed by an equivalent explicit page-level
statement. The chair name and a separate explanation of pack contents do not
make an otherwise unqualified weight or load safe: a customer can reasonably
read it as the selected pack's value. Open/folded/packed-product dimensions are
handled by the separate state-scope owner and identify one chair when their
state label is preserved. This is a catalog-unit control, not a wording
preference.

## Lenient Score

Lenient is independent of strict. It requires the complete selected SKU range,
the declared draft/import staging state, schema, grouping, options and prices,
correct product identity, a clear explanation of 1-Pack versus 2-Pack where
applicable, usable content structure, and at least partial fidelity for every
paired claim owner. The range and staging checks are hard delivery requirements
because the public task requires the selected range to remain intact and the
file to stay ready for import before publication. It does not threshold the
strict score.

## Judge Operation

The LLM judge must cite bound candidate evidence and source/reference evidence
for every criterion. Invalid extra citations are ignored only when sufficient
valid evidence remains. New submissions use the standard `LLM_JUDGE_*` fresh
Responses-compatible runtime; replay requires an exact request-bound response.
Infrastructure failure is unmeasured, never a candidate zero.
