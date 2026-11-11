# Scoring Contract

The verifier reads only `electrical_drawings.dxf` and the reviewed hidden facts. It does not inspect model identity, skill mounting, or trajectory text. The checked-in Golden is a union crop of the real case-source DXF, retained as native entities and coordinates; it is not a facts-generated redraw.

## Better-Have Score

The continuous strict score is:

```text
valid_editable_dxf * (0.50 * semantic_content + 0.50 * diagram_topology)
```

The equal split reflects two co-essential engineering responsibilities. Panel
and circuit data must be electrically faithful, while the native connections,
sheet organization, and editable geometry must remain usable as a drawing set.
A text-rich DXF without coherent topology and a well-connected drawing with
wrong ratings are both materially incomplete. The 50/50 split gives neither
failure class the ability to hide behind the other; it is a relative
responsibility allocation, not a claim that nearby splits are invalid.

Both dimensions are normalized by the current parser ceiling measured on the
native reference drawing and declared in `ground_truth.json`. The same transform
applies to every candidate; no artifact hash or Golden-only branch is used.

semantic_content is 55% square-root-scaled exact panel/circuit-row F1, 20% coherent partial-row F1, 10% sheet-anchor recall, and 15% source-bound semantic review. The semantic review has three simple owners: sheet ownership, device/symbol meaning, and connection meaning. Incoming-supply information is scored once, inside diagram_topology. The coverage curve gives diminishing returns after the first verified complete rows; zero exact rows still receive zero exact-row credit. A row is exact only when its panel, identifier, load, capacity, phase, breaker, and conductor/conduit text are all present without conflicting candidate values in the same local drawing region. A coherent partial row must have one unique circuit key, match at least four of the five row fields in that same region, and include the load name, breaker, and conductor/conduit fields. Raw per-field matches remain diagnostics and do not earn reward by themselves.

diagram_topology is 65% coherent geometry F1, 20% sheet completeness, 10% complete incoming-panel accuracy, 3% endpoint connectivity, and 2% junction density. Sheet completeness is 60% complete-sheet ratio plus 40% anchor recall. Connectivity and junction density each use a binary gate requiring at least one actually matched circuit; they are not multiplied by circuit recall. Complete incoming-panel accuracy is the fraction of the three reviewed panels with all incoming fields correctly represented in their panel region; it is not multiplied by a second coverage factor. A parseable native DXF with no raster, underlay, or raster-equivalent trace is a gate rather than an additive score; vector_delivery remains a diagnostic only.

## Must-Have Score

The lenient score is a delivery contract with a reconstruction-quality floor. It is
`1` only when all conditions hold:

- the deliverable is a valid DXF with an `ENTITIES` section and `EOF`;
- no image, image definition, or underlay entity/data is present;
- no raster-equivalent scanline, pixel-run, or image-contour geometry is present;
- all four issued sheets are represented by their visible titles, identifiers, and native content;
- all three reviewed panels are represented;
- coherent partial-row precision and recall are at least `0.30`;
- incoming-field accuracy is at least `0.50`; and
- topology score is at least `0.30`; and
- the source-bound semantic review confirms sheet ownership, device/symbol
  meaning, and connection meaning from local native drawing evidence.

The coherent-row and topology floors use the same hidden reviewed facts as strict, so
lenient is a coarser binary view of that evidence rather than an independent score.
Otherwise it is `0`. The primary `reward` aliases the strict score.


## Equivalence And Provenance

Room labels accept numbered or ranged suffixes. Incoming-panel information is
scored only in topology; circuit recall is not multiplied into incoming,
connection, or junction credit. Breaker continuation text belongs to the same
column and preceding breaker until the next breaker begins. Capacity accepts
equivalent numeric forms such as `0.8`, `0.80`, and a value with its unit.

The Golden is a native crop of the engineering source DXF. The evaluator does
not infer whether a candidate was manually redrawn from PNG. It measures native
geometry, symbols, connections, and visible content. Standard DXF class
declarations and unreferenced definitions outside `ENTITIES` are not treated as
embedded raster content.
