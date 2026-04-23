# DXF Analysis Report

## Raw File Organization

- Runtime for parse + extraction: `2.61s`
- Primitive types are dominated by `LINE` with `58128` entities, followed by `LWPOLYLINE`, `ELLIPSE`, `HATCH`, and `ARC`.
- Scoped target primitives total `34834` entities with an estimated drawable length of `1144751.426` units.
- Estimated consumed target length is `228196.808` units, or `19.9%` of scoped drawable length.

## Target Family Counts

- Walls extracted: `274`
- Columns extracted: `572`
- Curtain walls extracted: `304`

## Connectivity Callouts

- Snap `0.1`: `20357` nodes, `7425` leaves, `9780` degree-2 nodes, `1196` degree-3 nodes, `1956` degree-4+ junctions.
- Snap `0.25`: `17143` nodes, `6707` leaves, `7471` degree-2 nodes, `833` degree-3 nodes, `2132` degree-4+ junctions.
- Snap `0.5`: `15039` nodes, `5427` leaves, `7338` degree-2 nodes, `662` degree-3 nodes, `1612` degree-4+ junctions.
- Snap `1.0`: `13201` nodes, `4302` leaves, `6838` degree-2 nodes, `708` degree-3 nodes, `1353` degree-4+ junctions.

## Interpretation

- The data behaves like a tokenization problem: direct closed carriers give obvious tokens, while wall linework requires graph-based closure recovery.
- Columns are the cleanest family because circles and compact closed polylines are abundant on column layers.
- Walls remain the hardest family because they are dominated by open linework, mixed drafting conventions, and high-degree junctions after snapping.
- Curtain wall layers are structurally regular and would benefit from a second-pass grid detector if coverage mattered more than turnaround time.

## Applied Category Theory Lens

- Treat raw primitives as generators in a low-level geometry category and closed polygons as composed morphisms that satisfy closure and orientation laws.
- Endpoint snapping is a quotient operation: nearby coordinates collapse into equivalence classes before composition is valid.
- Family typing acts like a functor from geometry into a typed architectural semantics layer, preserving structure while changing the vocabulary.

## ML Theory Lens

- The geometric pipeline is the low-entropy scaffold: closure, winding, validity, and layer priors are stable structure.
- Learned tolerance, family disambiguation, and correction-on-feedback would be the high-entropy adaptation layer in production.
- A future GNN would not replace geometry; it would propagate uncertainty and drafting-style context over the object graph produced here.