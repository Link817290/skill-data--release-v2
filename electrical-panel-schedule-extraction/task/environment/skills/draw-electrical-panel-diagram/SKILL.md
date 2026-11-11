---
name: draw-electrical-panel-diagram
description: Inspect and reconstruct multi-sheet electrical drawings from raster references. Use for reading dense notes, panel diagrams, schedules, and electrical floor plans before drafting them as CAD; combine with draft-native-electrical-dxf and check-electrical-drawing-set when the deliverable is an editable DXF.
---

# Read the Electrical Drawing Set

Treat the supplied sheets as one coordinated electrical set. Read their electrical meaning before
choosing CAD entities. Use `draft-native-electrical-dxf` for construction and
`check-electrical-drawing-set` for the final review.

## Inspect every sheet

- Open every full sheet first and identify its title, scale, orientation, major regions, and relation
  to the other sheets.
- For dense text or symbols, create enlarged overlapping views in a temporary directory:

  ```bash
  python3 scripts/prepare_reference_views.py IMAGE --output-dir /tmp/SHEET \
    --rows 3 --cols 3 --overlap 0.10 --scale 2
  ```

  Pass one image at a time. Use the overview to locate important regions, then inspect the tiles
  containing unresolved notes, rows, symbols, or connections. Do not spend the drawing budget on
  decorative regions that do not change the electrical meaning.
- Read the notes and legend before drawing the plans. Use them to interpret symbols, line types,
  and abbreviations, then check those interpretations against the panel schedule and plan labels.
- On each panel diagram, inventory the panel boundary, incoming supply, main device, bus, outgoing
  branches, protective devices, headers, circuit rows, ratings, and conductor/conduit notes.
- Before drafting, make a temporary row ledger for the panel sheet. Give every visible nonblank
  circuit one row with its panel, identifier, load, capacity, phase, breaker, and
  conductor/conduit value. Resolve blank cells and split text from the image now; a visually
  convincing table with omitted columns is not a completed transcription.
- On each plan, inventory rooms and boundaries first, then panels, fixtures, receptacles, switches,
  equipment, tags, home runs, circuit labels, and the lines connecting them.

## Resolve ownership

- Use table columns, row alignment, leader endpoints, wire endpoints, junctions, and enclosing
  boundaries to associate text with electrical objects. Proximity alone is not ownership.
- Follow a branch from its source to its endpoint before recording its label. Distinguish connected
  crossings from unconnected crossings and preserve junction marks.
- Keep each circuit row intact. Do not borrow a rating, phase, load, or cable specification from an
  adjacent row or panel.
- Treat OCR as a candidate reading only. Confirm it against the enlarged image, repeated notation,
  and the object's position before using it.
- A printed value may be split across several text entities or continue on the next line. Join
  those pieces only when their alignment and spacing clearly show they are one value. Leave
  blanks, spare rows, ellipses, and unreadable text as they appear; never fill them from a guess.

## Prepare to draft

- Make a per-sheet checklist of the semantic objects and their connections before writing the DXF.
  Treat the panel row ledger as the controlling checklist: do not replace unresolved cells with
  generic labels or leave them for a cosmetic pass.
- Timebox the first inspection pass. Once every sheet has a checklist, start drafting and return to
  enlarged views only to resolve specific uncertainties.
- If time is limited, cover every sheet, finish the panel ledger, and preserve correctly read
  electrical relationships before tracing borders, hatches, decoration, or other cosmetic detail.
