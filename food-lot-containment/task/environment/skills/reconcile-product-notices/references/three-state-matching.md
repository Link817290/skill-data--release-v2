# Three-state identification

A match requires the product identity and every applicable predicate supported by the notice. Evaluate each known predicate, retaining whether the evidence is known, missing or contradictory. Use inclusive endpoints when the notice says through; keep sales, best-before and coding predicates separately typed.

- `included`: all required predicates are known and satisfied.
- `outside`: at least one known predicate contradicts the scoped rule.
- `review`: no known predicate excludes the observation, but required evidence is missing or invalid.

An `outside` result is outside that one rule, not proof of overall safety. Evaluate the other effective rules before drawing a product-level conclusion. A `review` result needs appropriate temporary control and evidence gathering, not automatic release.

The helper accepts JSON with `observation`, `equals`, optional `date` (`field`, `start`, `end`) and optional `code` (`field`, `prefix`, `min`, `max`, optional `width`). It does not discover the correct predicates or authorize physical disposition. Dates must be ISO dates and dimensions must be established from source evidence.
