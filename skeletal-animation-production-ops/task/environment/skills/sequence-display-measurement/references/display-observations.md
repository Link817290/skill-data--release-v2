# Display observation matrix

| Claim | Minimum evidence | Common ambiguity |
|---|---|---|
| Original artwork is used | Actual runtime texture pixels versus source pixels | A correct unused resource can coexist with a replacement texture |
| Anchor is correct | Image anchor transformed to world coordinates | Centering and offset can be equivalent |
| Direction is correct | Forward basis and travel vector in one space | Angle wrap, mirrored scale, parent rotation |
| Effect is visible | Ancestor visibility, effective color, texture alpha and sample time | Intentionally transparent source frame |
| Timing matches contract | Engine timestamps and frame indices over interval | Call time versus next update |
| Blend is appropriate | Same image/time on contrasting backgrounds | Layered source and flattened output differ |

For each row record contract reference, measurement, tolerance, artifact path and unresolved ambiguity. A tolerance must come from the delivery contract or a documented sampling bound. This table identifies evidence; it does not select settings or a repair.
