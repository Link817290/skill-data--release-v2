# Product families, variants and physical units

## Use three identities

1. **Product page:** the shared customer proposition and shared facts.
2. **Orderable variant:** an actual SKU with an observed option tuple and its price.
3. **Physical sales unit:** what one purchased SKU supplies.

These do not collapse to a single key. Two near-identical titles may refer to different frame designs. One product may have several real model-code prefixes because packs use separate SKUs. A two-person bench remains one bench; it is not a two-bench pack.

## Build observed tuples, not combinations

Suppose the handover contains:

| SKU | Color | Pack |
|---|---|---|
| Q10-SAND | Sand | Single |
| Q20-SAND | Sand | Pair |
| Q10-INK | Ink | Single |

There are three variants. Generating `Color × Pack` invents an unselected Ink pair. Missing combinations may reflect commercial assortment, not erroneous data.

Keep one consistent product handle for the three observed tuples. Preserve the full SKU as text; slash, leading zero or hyphen can be identity-bearing. Normalize customer option capitalization only, not underlying SKU identifiers.

## Decide the option schema

- A meaningful variable such as Color stays an option even when the launch selects one color.
- A constant “One Size” or “Single unit” dimension often adds no customer choice. Follow the requested storefront convention instead of mechanically copying supplier scaffolding.
- If some variants have pack choices, keep the option names consistent for the product; do not put the pack count into a color label.
- A compound color such as “Forest/Stone” can be one color option, not two independently combinable colors.
- Pack pricing is supplied per sellable SKU. Do not multiply a single-unit price to invent a bundle price.

## Identity checks

Independently compare the selected tuple set with the output tuple set. Compare identifiers before comparing row counts: duplicating one SKU and omitting another preserves the count but changes the range. Check both directions: no selected SKU omitted, no output SKU unsupported.

Then check product grouping. A rename of a handle is harmless when grouping is unchanged. A split product or a merged pair of different designs changes the merchandising proposition even if every SKU remains present.
