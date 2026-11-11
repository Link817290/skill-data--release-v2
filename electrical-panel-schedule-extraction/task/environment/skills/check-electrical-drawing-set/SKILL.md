---
name: check-electrical-drawing-set
description: Review an editable electrical DXF against raster reference sheets. Use after drafting to check sheet coverage, circuit and panel relationships, native CAD structure, text fidelity, and removal of raster-equivalent content before delivery.
---

# Check the Electrical Drawing Set

Review meaning and structure before appearance.

## Compare sheet by sheet

- Reopen or parse the saved DXF and inspect each sheet region separately.
- Confirm every reference sheet has its own frame, title, substantive native geometry, and readable
  text. A title beside unrelated filler geometry is not sheet coverage.
- For each panel, trace the incoming feeder through the main device and bus, then follow every branch
  to its circuit row. Confirm identifiers, loads, ratings, phases, breakers, and cables remain with
  the correct panel and row.
- Reconstruct a final row ledger from the DXF text and compare it line by line with the temporary
  image ledger. Check that no nonblank source row or required cell disappeared during drafting and
  that plan circuit tags were not mistaken for schedule rows.
- For each plan, compare room boundaries, device locations, circuit tags, home runs, junctions, and
  endpoints against the full sheet and enlarged views.

## Inspect CAD integrity

- Confirm the file has a real `ENTITIES` section, a closing `ENDSEC`, and `EOF`, and can be
  reopened by a DXF parser or CAD application.
- Confirm electrical connections share endpoints where intended and that repeated symbols are
  sensible native entities or blocks.
- Search for and remove `IMAGE`, image definitions, PDF/DGN/DWF underlays, embedded image data, and
  references to the source PNGs.
- Reject dense pixel-run, scanline, contour, or color-cell geometry even when it uses nominally
  editable entities. Text must remain text and electrical objects must remain recognizable objects.

Keep temporary crops, OCR files, and generation scripts outside the final output directory. Deliver
only the requested DXF after resolving omissions and misplaced relationships.
When time is short, repair missing or incorrect panel fields and broken connections before adding
more architectural or decorative geometry.
