# Findings

This is the short, evidence-first summary for the DXF reconstruction
project. For the broader research direction this work points toward, see
[`research_extension.md`](research_extension.md).

## Scope

The input is primitive-level CAD geometry: roughly 67,000 DXF entities
across roughly 111 layers, with no object grouping metadata. The output
is closed polygons grouped as walls, columns, and curtain walls, each
retaining raw `source_layers` and emitted as clockwise vertices in the
JSON deliverable.

The direct solution treats the file as a geometry tokenizer.

| Concept | DXF form |
|---|---|
| characters | primitives |
| closure rules | endpoints connect, CW winding |
| tokens | closed polygons |
| family classification | family inference from layers plus geometry |
| residual metadata | `source_layers` / `source_kind` |

That framing keeps the runnable solver concrete: recover closure,
validate rings, infer the scoped family, and preserve provenance.

## What The Solver Handles

The solver path is geometric and reproducible:

- parse raw DXF primitives with the standard library
- recover closed carriers directly
- recover additional faces from a snapped endpoint graph
- parse scoped `HATCH` boundary paths as direct polygon carriers
- preserve `source_layers` and `source_kind` for every polygon

That is enough to produce the required JSON and SVG overlay.

## Findings From The File

### HATCH Is A First-Class Carrier

`HATCH` is not decoration in this file. It is an area-fill primitive
whose boundary paths often describe the same physical walls and columns
that outline layers describe with linework.

The solver treats scoped HATCH boundary paths as direct polygon
carriers. That lets filled wall and column regions enter the same
closed-polygon representation as circles, closed polylines, and graph
faces.

The output still uses one polygon representation downstream. The
distinction is carried in `source_kind="direct_hatch"` and the raw
companion layer in `source_layers`.

### Pool For Geometry, Tag For Provenance

Layer variants and carrier choices are useful geometry signals, but they
should not be collapsed without trace.

Examples:

- `A-GLAZING MULLION` and `A-GLAZING-MULLION` overlap spatially but use
  different primitive carriers.
- Wall and column HATCH companions describe filled regions that pair
  naturally with outline layers.
- A recovered polygon from `A-EXTERNAL WALL HATCH` should remain tagged
  to that layer, not rewritten as `A-EXTERNAL WALL`.

The practical rule is:

> pool for geometry, tag for provenance

### Merge Decisions Split Into Two Kinds

The merge problem is not one uniform task.

- **Programmatic merges** are decided from provenance and nearly
  degenerate geometry, such as duplicate carriers of the same local
  panel.
- **Contextual merges** require neighborhood reasoning, especially for
  fragmented wall runs.

On this file, curtain-wall merge candidates are mostly programmatic.
Wall merge candidates are mostly contextual. That is why the merge lab
is useful as a review surface rather than just a debugging page.

### Family Behavior Differs

- Columns mostly behave like direct closed carriers plus duplicate
  overlap cleanup.
- Walls behave like continuity through fragmented linework and companion
  HATCH fills.
- Curtain walls behave like local panels that would benefit from a grid
  detector if coverage mattered more than turnaround time.

## Extension Path

The next useful work should stay concrete:

1. Add exact bulge handling for all polyline curvature.
2. Add hole-aware HATCH assembly instead of skipping inner/default paths.
3. Add wall-specific merge logic for adjacent thin faces.
4. Add a curtain-wall grid detector.
5. Replace the current source-entity coverage proxy with exact
   primitive-length-inside-output-polygon scoring.
6. Use merge-lab labels to train a small, interpretable pair scorer only
   after the geometric scaffold is stable.

The important boundary is that learned components should sit above the
closed-polygon scaffold. They should not replace deterministic closure,
winding, layer scoping, or provenance.

## Reading Order

For a reviewer or interview conversation:

1. [`../../DESIGN.md`](../../DESIGN.md)
2. [`../process/layer_normalization_analysis.md`](../process/layer_normalization_analysis.md)
3. [`programmatic_vs_contextual_merges.md`](programmatic_vs_contextual_merges.md)
4. [`research_extension.md`](research_extension.md)
