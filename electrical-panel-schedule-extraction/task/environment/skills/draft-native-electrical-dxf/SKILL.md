---
name: draft-native-electrical-dxf
description: Draft electrical notes, panel one-lines, schedules, and floor plans as semantic native DXF geometry. Use after raster electrical sheets have been inspected and the required objects, labels, circuit rows, and connections are understood.
---

# Draft Native Electrical CAD

Build a CAD drawing whose entities represent electrical objects, not the source image's pixels.

## Do not make a vectorized screenshot

- Never convert non-white pixels, scanlines, color runs, antialiasing contours, connected image
  components, or glyph outlines directly into DXF geometry.
- Do not use dense `LINE`, `SOLID`, `HATCH`, or polyline fields to reproduce the raster appearance.
  Such a file may be technically editable but it is not an electrical CAD redraw.
- When a detail cannot be read confidently, omit or mark that detail rather than replacing the
  entire sheet with an automatic trace. A smaller semantic redraw is more useful than a
  pixel-faithful facsimile.

## Establish the drawing

- Assign a stable origin and scale to each sheet region and keep the regions separated.
- Create descriptive layers for sheet frames, architecture, panels, wiring, devices, symbols,
  annotations, and dimensions as appropriate.
- Use native entities according to meaning: `LINE`/`LWPOLYLINE` for boundaries and conductors,
  `ARC`/`CIRCLE` for curved symbols, `INSERT` for repeated devices, and `TEXT`/`MTEXT` for
  readable labels and notes.

## Draw in dependency order

1. Create a valid DXF immediately, then draw all sheet frames, titles, and major regions so the
   complete set has an explicit structure.
2. Draw panel boundaries, incoming feeders, main devices, buses, and outgoing branch skeletons.
3. Complete the panel sheet from the row ledger before adding plan detail. Add one branch and
   protective-device symbol for each circuit row, then place that row's identifier, load, capacity,
   phase, breaker, and conductor/conduit text together. Never trade these cells for denser borders
   or decorative linework.
4. Draw plan boundaries and room divisions, place electrical devices, and connect wires or home runs
   to the correct symbols and labels.
5. Add notes and legend symbols as native text and reusable geometry. Add cosmetic detail last.

Keep shared endpoints coincident. Do not represent a connection by two lines that merely look close,
and do not join lines at a crossing unless the reference shows a junction.
Write a valid output file as soon as the sheet frames exist and update it after each substantive
sheet. An interrupted run should retain the completed semantic work instead of an empty output
directory.

## Preserve information

- Transcribe visible identifiers, ratings, units, phases, cable and conduit specifications, room
  names, and notes. Preserve meaningful punctuation and line breaks.
- Keep text as `TEXT` or `MTEXT`; do not outline letters as geometry.
- Keep each label in the same local region as the object or circuit row it describes.
- Reuse blocks for repeated symbols when practical, while leaving instances editable.
