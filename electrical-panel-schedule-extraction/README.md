# Electrical Drawing Set Redraw

This task uses four redacted, real-project electrical sheets as raster references: design notes/legend (S-01), panel system diagram (S-02), and first- and second-floor plans (S-03/S-04). The agent must redraw the complete set as one editable DXF using only the PNGs in the workspace. The source DXF is intentionally withheld from the agent.

The Golden and reference solution are an exact model-space union crop of the authoritative case-source DXF for the four reviewed regions. The crop operation only removes entities outside those windows; it does not redraw or synthesize CAD geometry. The source checksum and crop windows are recorded in `dataset.toml`.

The verifier parses the submitted DXF directly. It checks valid CAD sections, native vector entities, sheet anchors, panel/circuit content, visible connections, and the absence of raster or underlay entities. The binary lenient lens requires a usable four-sheet drawing set and a modest coherent-row/topology floor; it is not a near-perfect-redraw threshold.

Run the package regression from the repository root:

```bash
python3 task/tests/validator.py golden/electrical_drawings.dxf
```

The package contains the released cropped Golden and its scoring facts. The
unredacted source drawing and internal crop pipeline are intentionally not part
of the actor-facing or release package.
