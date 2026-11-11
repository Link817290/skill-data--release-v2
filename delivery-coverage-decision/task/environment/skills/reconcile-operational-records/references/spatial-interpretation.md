# Spatial interpretation before service analysis

## Coordinates and snapping

Treat the CRS, axis order and units as separate fields. A longitude/latitude-looking pair does not establish a CRS. Apply a declared transformation into an appropriate metric system before measuring; explicitly configure axis conventions rather than relying on library defaults. Preserve original coordinates and transform metadata for disputed records.

Validate at each boundary: parseability, finite numbers, declared geographic ranges, successful projection and finite projected results. A supported CRS label does not make its coordinate payload valid; some transformation libraries return infinity instead of raising by default. Enable transformation error checks where available. Apply the material's exception policy to the affected record and continue processing unrelated valid records. Distinguish an invalid coordinate from a valid location outside the service radius: only the former is a data exception. Test the reader and independent checker on the same invalid payload; matching crashes do not validate the policy.

Choose the snapping target required by the material: graph node, traversable edge, entrance or address point. These are different models. A node snapped across an impassable barrier may be geometrically near but operationally unreachable. If the supplied model deliberately uses nearest nodes, follow it and disclose that limitation instead of silently replacing the model.

Keep unrounded distances for eligibility unless a normalization rule explicitly defines otherwise. For a threshold T, test values just below, exactly at and just above T using the stated inclusive/exclusive rule. Use a deterministic tie rule if several targets are equally near; do not let CSV row order decide. Record unsupported CRS and missing coordinates as data exceptions rather than guessed positions.

## Directed travel and service time

Maintain physical segment identity separately from directed traversal arcs. Parallel roads can connect the same nodes with different costs or permissions. A segment closure may remove both arcs; an asymmetric restriction may remove only one. Preserve segment identifiers in path witnesses so a checker can distinguish these cases.

List every component of promised service time: preparation, legal network travel, access legs and other documented handling. Specify the stage of rounding. Two segments of 1.2 seconds cost 4 seconds when each is rounded upward, but 3 seconds when the route is rounded once. This can change a boundary decision.

A disconnected destination, a closed site, a site lacking capability and a route exceeding a deadline are different reasons for ineligibility. An eligible order left unassigned by shared capacity is a different outcome again. Keep the distinctions in computation even if the report groups them for readability.

## Check semantic consistency

Independently recompute a small set of legal path costs before accepting bulk results. Include relevant directional, closure and threshold cases. When an efficient implementation collapses parallel arcs, verify that the retained arc is legal and cheapest in that scenario, not merely the first arc encountered.

Use the same extent, units and legend when comparing scenario maps. An order-point plot is evidence about supplied demand, not a continuous service-area promise. Isolines or filled polygons require a separate interpolation/network coverage model and should not be inferred from point assignments alone.
