# Identity and table grain

Choose keys from the business question. A product key may combine responsible company, brand, description, package and available identifier. A distribution relationship adds the channel; a dated scope adds the date semantics and interval. These grains must not share one deduplication rule.

One identifier appearing at two distributors is one product and two relationships. A missing identifier is not zero and is not permission to merge all unidentified items. Use the remaining explicit identity fields and keep uncertainty visible.

Preserve multipack expressions until the packing configuration is defined. A string containing a pack count and weight does not, by itself, prove whether the weight is per inner unit or total. Do not convert identification strings into inventory quantities.

When reading merged tables, inspect the original span. Expand a row-spanning channel only over its stated rows. Plain text extraction often loses this scope. Blank cells without a span must remain blank unless another source explicitly establishes the relationship.

Normalize typography and equivalent representations separately from identifiers. Whitespace, curly apostrophes and official state names versus abbreviations can be equivalent. Different UPC digits, packages or date kinds cannot. Retain the original value beside normalization during authoring so every transformation can be checked.

For controlled date labels, normalize case, spacing and hyphens without merging distinct business meanings such as sale periods and use-by dates. A source reference must support the actual product, package and relationship on that row. A valid document identifier alone is insufficient when that document covers a different pack or customer. For additions, compare the old and new membership sets before attaching the amendment as evidence. Test a correct alternate spelling and a plausible but unrelated source reference separately.
