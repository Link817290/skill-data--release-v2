---
name: reconcile-product-notices
description: Reconcile successive product withdrawal or recall notices into a traceable identification register, preserving product variants, date meanings and downstream relationships. Use for notice-based scope analysis; do not infer inventory or manufacturing genealogy from announcements alone.
---

# Reconcile product notices

Represent each notice as a dated scope assertion. Separate the date of the business action from later publication, the product identifier from the channel, and package dates from sales windows. Read [notice changes](references/notice-changes.md) when combining announcements; read [identity and table grain](references/identity-and-grain.md) before expanding or deduplicating rows.

Build one record for each materially different identification rule. A later partial list may add variants without withdrawing earlier ones. Record the actual operation supported by the text: addition, replacement of a specified subset, correction, or cancellation. Do not infer full replacement from a newer date.

Keep links to the source row and paragraph establishing each predicate. Do not force a consumer date window into a manufacturing-lot field. For incomplete product observations, read [three-state matching](references/three-state-matching.md); `scripts/match_scope.py` can evaluate explicit equality, date and code predicates without treating missing values as safe.

Before finalizing, reconcile the number of source rows, distinct products, packaging variants and channel relationships. Verify an unaffected boundary, an included boundary, an unknown observation, and a later partial amendment. These are method checks, not fabricated operational records.
