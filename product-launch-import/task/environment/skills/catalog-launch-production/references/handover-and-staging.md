# Handover authority and launch state

## Separate three kinds of data

| Kind | Typical authority | Consequence |
|---|---|---|
| Physical product fact | Manufacturer specification for the exact model | Supports a factual customer claim, not a merchant inventory balance |
| Planned commercial setting | Merchant's launch brief and price handover | Can set future retail price, tax treatment and workflow state |
| Observed operational record | Warehouse count, barcode master, measured carton record | Required to assert those operational quantities as known |

A supplier price does not automatically become the merchant's selling price. If the handover explicitly adopts it, carry the planned amount and currency; do not invent a currency conversion, margin or discount. Compare-at prices imply a promotion relationship: a blank compare-at field is different from zero or the supplier's suggested retail price.

## Stage the record deliberately

New-draft imports and updates to live products differ. For a new draft, the merchant may defer media or warehouse configuration. For an update, an empty column may overwrite existing content: obtain the intended update scope before reusing a new-product export.

Decide separately:

- product status;
- availability on the online channel;
- inventory tracking;
- overselling policy;
- fulfillment service;
- physical shipping and taxation.

An untracked variant can still sell without a quantity-based guard. A `deny` policy is not a substitute for inventory tracking. A draft and unpublished product is a useful staging boundary, but the warehouse and publishing team must finish their own setup before launch. Do not add fake zero stock as a placeholder; zero is an actual quantity.

## Example

A planned US launch lists a bottle at USD 28 with no warehouse feed. A supplier says “available” on its website. The correct import can stage the merchant's USD 28 draft without asserting merchant stock or a delivery date. The supplier availability statement alone cannot establish either.

The package's public handover may prescribe stricter defaults than a generic platform example. Follow the actual business contract, not a remembered template.
