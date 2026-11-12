# CSV serialization and static checks

Use the current supplied interface as the schema authority. Platform documentation and downloadable examples can use different generation-specific headings. Do not mix legacy headers with a current template merely because both sound familiar.

## Row roles and dependencies

The handle groups rows into a product. The first row carries shared product title, description and taxonomy; continuation rows carry the same handle and their own option tuple, SKU and price. Keep the product's rows contiguous. Apply the handover's rule for which shared cells should remain empty on continuation rows.

Option names and values work together. A populated SKU does not rescue a missing variant option. Up to the platform's supported option count can be used, but do not add empty dimensions just to match a supplier sheet. Inventory or fulfillment columns can have dependencies; avoid sending an incomplete optional feature bundle.

An explicitly supplied price must be numeric in the store currency, without a currency symbol. Missing values should not be turned into zero. Booleans and enum values should use the actual template's tokens. Draft status and channel publication are separate fields.

## Serialization

Use a CSV library with UTF-8 encoding and quote handling. HTML and tags contain commas; manual string concatenation can shift columns. Do not place spreadsheet formulas into monetary cells. Preserve SKU text rather than passing it through numeric inference.

HTML descriptions should use simple allowed structural elements such as paragraphs and lists, with text escaped before insertion. Do not ship script/event handlers or a whole HTML document with internal tools and notes.

## Three independent checks

1. **Transport/interface:** parsing, exact column contract, row lengths, encoding and option dependencies.
2. **Commercial data:** exact selected SKU tuples, prices, page grouping and staging defaults.
3. **Meaning:** factual identity, units, pack contents and justified claims.

The included helper addresses the first layer and some grouping invariants only. A valid file may still contain a wrong price or unsupported claim. A successful import can still publish bad content. Conversely, without a live store import, report only static readiness rather than “successfully imported.”
