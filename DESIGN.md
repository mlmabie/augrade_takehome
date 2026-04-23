# Design Note

## Approach

I treated the DXF problem as a tokenization problem over raw geometry:

1. parse the DXF into primitive carriers
2. recover obvious closed tokens directly
3. recover additional tokens by composing open primitives through endpoint closure
4. classify tokens by family using layer priors plus lightweight geometric filters

The implementation in [`tokenize_dxf.py`](/Users/malachi/augrade_takehome/tokenize_dxf.py) stays stdlib-only so it runs immediately in this environment without dependency installation.

## Per-Family Strategy

### Walls

- Use direct closed geometry when present.
- Flatten open `LINE`, `ARC`, and open polyline work into segments.
- Snap endpoints at a configurable tolerance.
- Build a planar half-edge structure and walk bounded faces.
- Keep faces that are simple, clockwise after normalization, and wall-like by area/aspect.

This is the hardest family because the file is dominated by open wall linework and mixed drafting conventions.

### Columns

- Prefer direct extraction from `CIRCLE`, compact closed polylines, and closed ellipses.
- Use graph faces only as a fallback.
- Filter by compactness, area, and bounding-box aspect ratio.

This family is much cleaner because the scoped column layers contain strong direct carriers.

### Curtain Walls / Glazing

- Extract closed mullion/panel rectangles directly.
- Recover additional faces from open glazing linework.
- Filter for small-to-medium elongated panels and framed rectangles.

This works reasonably for local panel extraction, but a stronger version would add explicit grid detection.

## Why This Algorithm

The core operation is polygon closure. In graph terms, that is face recovery on a snapped endpoint graph. That gives a direct bridge from:

- primitive endpoints
- to compositional closure
- to polygon tokens

This is the geometric analogue of tokenizer composition: characters become tokens once local composition constraints are satisfied.

## Failure Modes

- Drafting gaps bigger than the snap tolerance leave open cycles unrecovered.
- Too-large snap tolerance can merge nearby but distinct corners.
- Treating bulged polylines as chords loses curved detail.
- Wall systems that should be merged across multiple local faces stay fragmented.
- Glazing arrays that are better understood as grids are only locally recovered.
- `HATCH` and `INSERT` information is currently unused for reconstruction.

## What I Would Add Next

1. Exact bulge handling for `LWPOLYLINE`.
2. `HATCH` boundary extraction as another direct-closure path.
3. Wall-specific merge logic for adjacent thin faces.
4. Glazing grid detection and grouping.
5. Primitive-length coverage scoring against the output polygons.
6. Learned tolerance and family disambiguation over ambiguous local regions.

## Tokenization / ML / Category-Theory Framing

The implementation is intentionally a low-entropy scaffold:

- closure rules
- winding rules
- simple validity checks
- layer-name priors

The production path would add a learned high-entropy layer on top:

- learned tolerance selection by drafting style
- ambiguous polygon disambiguation with sparse interpretable features
- graph-based propagation over object tokens
- correction-driven adaptation from reviewer feedback
- rewrite-invariance under drafting-convention symmetries as a training-time augmentation, not just a post-hoc validation check

The category-theory view is useful but should stay practical:

- primitives are generators
- closure composes them into admissible polygons
- snapping forms equivalence classes over nearby endpoints
- family typing maps geometry into a typed semantics space without discarding provenance

That is the right interview pivot: demonstrate the geometry cleanly, then explain how a learned relational layer would sit on top of it rather than pretending geometry alone solves the full production problem.
