# Units and bounds

Use the device's documented native density when it defines one; a marketed
resolution may be rounded. Multiplying by a nominal dpi divided by an inch
conversion can disagree with the controller's exact dots-per-millimetre value.
Preserve requested physical extent, controller extent and maximum separately.

Validate the converted setting against the selected model's range. An out-of-range
request is not repaired by silently clipping to the maximum. Determine whether the
business allows changing the output, material or machine; retain a hold until the
appropriate decision exists.

A starting adjustment is distinct from a validated process setting. Do not infer
a universal speed, pressure or temperature optimum from a reference start table.
Parameters derived from actual trials remain blank or conditional until tested.

Perform a reverse conversion as an independent check. On format migration, test
physical dimensions; reusing a point-based layout at a different density changes
size even if the data and text are unchanged.
