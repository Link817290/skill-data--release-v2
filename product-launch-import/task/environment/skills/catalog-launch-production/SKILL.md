---
name: catalog-launch-production
description: Produce a storefront-ready product import from a merchant assortment handover and mixed supplier specifications. Use for new product launches with sparse variants, packs, multilingual facts, customer copy, and staged fulfillment setup.
---

# Catalog launch production

Create the requested import artifact, not a review memo. Keep a small private working map while drafting; the customer-facing deliverable should contain only store content.

1. Read the handover as a division of authority: assortment and retail plan, product evidence, then platform interface. Distinguish planned store settings from facts about physical goods or warehouse stock. See [handover and staging](references/handover-and-staging.md).
2. Establish a product family, an orderable variant tuple, and a physical sales unit before writing a row. Preserve real SKU punctuation and the observed sparse set of tuples. See [variant modeling](references/variant-modeling.md).
3. Build an evidence ledger for claims: fact, unit, scope, qualification, product/variant applicability. Resolve contradictions conservatively without silently repairing source numbers. Translate meaning, not just labels. See [copy and measurement](references/copy-and-measurement.md).
4. Write useful English copy per product. A short use-case paragraph plus specific facts is often enough. Describe set contents when a pack or shared-use object can be misunderstood. Avoid unsupported performance, stock, shipping or regulatory assurances.
5. Serialize using the actual supplied platform headers. Product rows and variant rows have different roles; missing data, blank cells and false/zero are not interchangeable. See [import mechanics](references/import-mechanics.md).
6. Run `python scripts/inspect_import.py products.csv --out import-check.json` privately. Then independently compare SKU/option/price tuples with the handover and reread each product's claims against its specifications. The helper checks mechanics, not product truth, complete assortment, live-store compatibility or legal claims.
7. Deliver only the requested files. A successful static check does not establish a successful platform import or publication.

If the sources disagree, use the strongest applicable fact and omit a nonessential disputed claim when the launch can still be completed. Do not create stock, barcode or packing data to fill optional fields. If an essential required field remains unresolved, state the precise blocker through the authorized handover channel rather than fabricate it.
