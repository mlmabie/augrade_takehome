# DXF Analysis Report

## Raw File Organization

- Runtime for parse + extraction: `2.71s`
- Primitive types are dominated by `LINE` with `58128` entities, followed by `LWPOLYLINE`, `ELLIPSE`, `HATCH`, and `ARC`.
- Scoped target primitives total `36827` entities with an estimated drawable length of `1967355.755` units.
- Source-entity coverage proxy is `1010862.297` units, or `51.4%` of scoped drawable length.
- Coverage caveat: this is a source-entity-length proxy, not the grader's exact primitive-length-inside-output-polygons metric.

## Target Family Counts

- Walls extracted: `1158`
- Columns extracted: `764`
- Curtain walls extracted: `304`
- Direct HATCH polygons extracted: `1453` from `2222` outer/external HATCH paths; `56` non-outer paths skipped as hole/default candidates.

## Connectivity Callouts

- Snap `0.1`: `20398` nodes, `7419` leaves, `9808` degree-2 nodes, `1208` degree-3 nodes, `1963` degree-4+ junctions.
- Snap `0.25`: `17181` nodes, `6696` leaves, `7499` degree-2 nodes, `848` degree-3 nodes, `2138` degree-4+ junctions.
- Snap `0.5`: `15077` nodes, `5417` leaves, `7365` degree-2 nodes, `676` degree-3 nodes, `1619` degree-4+ junctions.
- Snap `1.0`: `13237` nodes, `4289` leaves, `6865` degree-2 nodes, `723` degree-3 nodes, `1360` degree-4+ junctions.

## Interpretation

- The data behaves like a tokenization problem: direct closed carriers give obvious tokens, while wall linework requires graph-based closure recovery.
- Columns combine strong direct carriers (circles, compact polylines) with companion-layer HATCH boundaries where those paths qualify as outer loops.
- Walls remain the hardest family because they are dominated by open linework, mixed drafting conventions, and high-degree junctions after snapping.
- Curtain wall layers are structurally regular and would benefit from a second-pass grid detector if coverage mattered more than turnaround time.

## Representation Lens

- Treat raw primitives as composable low-level geometry and closed polygons as tokens that satisfy closure and orientation laws.
- Endpoint snapping collapses nearby coordinates before composition is valid.
- Family typing maps geometry into architectural vocabulary while preserving source-layer provenance.

## Learning Extension

- The geometric pipeline owns deterministic structure: closure, winding, validity, and layer priors.
- Learned tolerance, family disambiguation, and correction-on-feedback belong above that layer.
- A future GNN would not replace geometry; it would propagate uncertainty and drafting-style context over the object graph produced here.
