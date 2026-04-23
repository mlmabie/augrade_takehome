# Design Note

## Approach

I treated the DXF problem as a tokenization problem over raw geometry:

1. parse the DXF into primitive carriers
2. recover obvious closed tokens directly
3. recover additional tokens by composing open primitives through endpoint closure
4. classify tokens by family using layer priors plus lightweight geometric filters

The implementation in [`tokenize_dxf.py`](tokenize_dxf.py) stays stdlib-only so it runs immediately in this environment without dependency installation. A thin library (`augrade/`) wraps the same functions for the dashboard, merge lab, REPL, and programmatic agent review; nothing new is implemented there, it just makes the extraction reusable from multiple entry points.

## Per-Family Strategy

### Walls

- Use direct closed geometry when present.
- Treat the explicit wall companion HATCH layers as geometry sources:
  `A-EXTERNAL WALL HATCH`, `A-MEZZANINE WALL FULL HATCH`,
  `A-WALL 1 HATCH`, and `A-WALL 2 HATCH`.
- Parse HATCH boundary paths directly, including polyline paths and
  edge paths made from LINE, circular ARC, and elliptic ARC edges.
- Flatten open `LINE`, `ARC`, and open polyline work into segments.
- Snap endpoints at a configurable tolerance (`--snap-tolerance`, accepts
  a scalar, a per-family map, or `adaptive`).
- Build a planar half-edge structure and walk bounded faces.
- Keep faces that are simple, clockwise after normalization, and wall-like by area/aspect.
- Preserve the companion layer in `source_layers`, so a polygon from
  `A-EXTERNAL WALL HATCH` stays tagged to that layer rather than being
  rewritten as `A-EXTERNAL WALL`.

This is the hardest family because the file is dominated by open wall
linework, mixed drafting conventions, and companion HATCH fills.

### Columns

- Prefer direct extraction from `CIRCLE`, compact closed polylines, and closed ellipses.
- Treat companion HATCH layers on scoped columns the same way as wall
  companions: `S-COLUMN HATCH`, `S-CONCRETE COLUMN HATCH`, and
  `S-STEEL COLUMN HATCH` contribute `direct_hatch` polygons when outer
  boundary paths parse (aligned with the brief’s fill-vs-outline note).
- Use graph faces only as a fallback.
- Filter by compactness, area, and bounding-box aspect ratio.

This family is much cleaner because the scoped column layers contain
strong direct carriers. Scoped HATCH companion boundaries are preserved
with their original HATCH layer in `source_layers`.

### Curtain Walls / Glazing

- Extract closed mullion/panel rectangles directly.
- Recover additional faces from open glazing linework.
- Filter for small-to-medium elongated panels and framed rectangles.

This works reasonably for local panel extraction, but a stronger version would add explicit grid detection. The supplied file did not expose companion HATCH carriers on the scoped curtain wall/glazing layers, so scoped HATCH extraction applies to walls and columns.

## Why This Algorithm

The core operation is polygon closure. In graph terms, that is face recovery on a snapped endpoint graph. That gives a direct bridge from:

- primitive endpoints
- to endpoint closure
- to polygon tokens

This is the geometric analogue of tokenizer composition: characters become tokens once local composition constraints are satisfied.

## Failure Modes

- Drafting gaps bigger than the snap tolerance leave open cycles unrecovered.
- Too-large snap tolerance can merge nearby but distinct corners.
- Treating bulged polylines as chords loses curved detail.
- HATCH holes are detected as non-outer/default paths and skipped;
  outer boundaries are emitted as independent polygon candidates.
- Wall systems that should be merged across multiple local faces stay fragmented.
- Glazing arrays that are better understood as grids are only locally recovered.
- `INSERT` information is currently unused for reconstruction.

## What I Would Add Next

1. Exact bulge handling for `LWPOLYLINE`.
2. Hole-aware HATCH polygon assembly instead of skipping inner paths.
3. Wall-specific merge logic for adjacent thin faces.
4. Glazing grid detection and grouping.
5. Exact overlap-based coverage scoring instead of the current source-entity proxy.
6. Learned tolerance and family disambiguation over ambiguous local regions.

## Research Direction

The implementation is intentionally a deterministic geometry layer:

- closure rules
- winding rules
- simple validity checks
- layer-name priors

The production path would add learned review components on top:

- learned tolerance selection by drafting style
- ambiguous polygon disambiguation with sparse interpretable features
- graph-based propagation over object tokens
- correction-driven adaptation from reviewer feedback
- rewrite-invariance under drafting-convention changes as a candidate training-time inductive bias

The broader principle is **pool for geometry, tag for provenance**:
layer variants, carrier choices, and decomposition conventions can all
contribute to geometry, but source layer and carrier kind must remain
visible for audit and future learning. See
[`reference/research/thesis.md`](reference/research/thesis.md) for the
short evidence-first thesis and
[`reference/research/research_extension.md`](reference/research/research_extension.md)
for the broader research direction.
