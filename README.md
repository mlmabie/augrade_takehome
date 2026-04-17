# DXF Primitive-to-Polygon Reconstruction

This repo solves the airport mezzanine take-home with a geometry-first pipeline that reconstructs closed polygons for:

- walls
- columns
- curtain walls / glazing

The core approach is intentionally simple and defensible:

- extract already-closed carriers directly
- flatten open linework into a snapped endpoint graph
- recover bounded faces as polygon candidates
- filter candidates by family-relevant geometry
- preserve `source_layers` so every output polygon stays traceable to the raw drafting layers that produced it

The main idea is:

> a DXF is a flat list of drawing primitives, so the task is to recover object-like tokens from geometric grammar rather than assume semantic objects already exist

That is why the code treats:

- primitives as carriers
- closure as the grammar
- polygons as tokens
- family inference as typed semantics on top of closure

## What To Run

### Minimal Solver

This is the simplest path that directly answers the assignment:

```bash
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out
```

Optional:

```bash
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out --snap-tolerance 0.5
```

This writes:

- `tokenization_output.json`
- `analysis_summary.json`
- `analysis_report.md`
- `raw_all.svg`
- `raw_target_families.svg`
- `extracted_overlay.svg`
- `walls.svg`
- `columns.svg`
- `curtain_walls.svg`
- `wall_connectivity_snap_0_5.svg`

### Full Review Bundle

This builds the reproducible analysis bundle around the same extraction:

```bash
python3 -m augrade.cli.pipeline "Airport Doors_MEZZ.dxf" out --snap-tolerance 0.5
```

This writes:

- extraction JSON
- SVG overlays
- provenance index
- static dashboard
- merge lab
- pipeline manifest

Main outputs:

- [`out/tokenization_output.json`](/Users/malachi/augrade_takehome/out/tokenization_output.json)
- [`out/extracted_overlay.svg`](/Users/malachi/augrade_takehome/out/extracted_overlay.svg)
- [`out/dashboard.html`](/Users/malachi/augrade_takehome/out/dashboard.html)
- [`out/merge_lab.html`](/Users/malachi/augrade_takehome/out/merge_lab.html)
- [`out/provenance_index.json`](/Users/malachi/augrade_takehome/out/provenance_index.json)

### Interactive REPL

The package also includes a stateful workbench:

```bash
python3 -m augrade.repl --input "Airport Doors_MEZZ.dxf" --output out
```

## Direct Take-Home Answer

The direct answer to the assignment is the extraction pipeline.

It currently:

- parses `LINE`, `ARC`, `CIRCLE`, `ELLIPSE`, `LWPOLYLINE`, and legacy `POLYLINE`
- extracts direct closed shapes
- recovers additional polygons from graph closure
- outputs clockwise polygon vertex lists
- reports runtime and primitive-consumption metrics
- produces visual overlays for review

On the supplied airport file, the current extraction produces:

- `274` walls
- `572` columns
- `304` curtain walls

These results are reproducible through the commands above.

## What The Analysis Added

The extra work was useful because it improved how the task is defined, not because it made the core algorithm gratuitously complicated.

Three things became clearer during the work:

### 1. Authored Variation Is Real Signal

The file is not just geometry plus random noise.

It contains authored variation:

- layer-schema differences
- carrier differences (`LINE` vs `LWPOLYLINE`, etc.)
- decomposition differences
- drafting-zone / phase differences

That matters because some apparent anomalies are not mistakes. They are alternative representations of the same or related objects.

### 2. Geometry And Grammar Matter Together

The geometric algorithm works because the file still obeys compositional rules:

- endpoints connect
- boundaries close
- some families repeat common footprint patterns

So the right mental model is not just “run geometry libraries.”  
It is “recover valid object tokens from a drawing grammar.”

### 3. Provenance Should Survive

Some normalization is useful, but provenance should not be erased.

The project therefore keeps the distinction:

- pool for geometry where helpful
- preserve raw source-layer provenance for audit, debugging, and future learning

That is important for:

- explaining the output to a human reviewer
- distinguishing drafting convention from structural signal
- defining future annotation workflows

## Supplementary Work

These are supplementary to the direct take-home answer, but they are not random extras. They support auditability, annotation, and future learned systems work.

### Normalization / Provenance

- [`augrade/normalize.py`](augrade/normalize.py)
- [`augrade/provenance.py`](augrade/provenance.py)
- [`reference/process/layer_etymology.md`](/Users/malachi/augrade_takehome/reference/process/layer_etymology.md)
- [`reference/process/layer_normalization_analysis.md`](/Users/malachi/augrade_takehome/reference/process/layer_normalization_analysis.md)

These were useful for understanding:

- naming anomalies
- layer-schema variants
- complementary representations
- why some surface differences should not be treated as separate object truth

### Dashboard / Merge Lab

- [`out/dashboard.html`](/Users/malachi/augrade_takehome/out/dashboard.html)
- [`out/merge_lab.html`](/Users/malachi/augrade_takehome/out/merge_lab.html)

These provide:

- reproducible visual review
- provenance inspection
- merge-candidate inspection
- expert labeling workflow

They are meant as review and annotation tools, not the centerpiece of the submission.

### Research / Theory Docs

- [`reference/process/PROCESS_JOURNAL.md`](/Users/malachi/augrade_takehome/reference/process/PROCESS_JOURNAL.md)
- [`reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](/Users/malachi/augrade_takehome/reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md)
- [`reference/experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](/Users/malachi/augrade_takehome/reference/experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md)
- [`reference/research/bigger_picture.md`](/Users/malachi/augrade_takehome/reference/research/bigger_picture.md)

These connect the take-home to the broader ML direction:

- geometric primitives as first useful tokens
- quotienting authored drafting rewrites
- typed object/relation state
- annotation workflows for future learned merge and graph models

## How To Explain This To A Structural Engineer

The simplest explanation is:

- a DXF does not store semantic wall or column objects
- it stores drafting primitives
- the task is to reconstruct the closed footprints a human would recognize as elements

Per family:

- columns are easiest because many are already circles or compact closed outlines
- curtain-wall elements often appear as regular panel footprints
- walls are hardest because they are mostly fragmented linework and junctions

The algorithm therefore:

1. takes the obvious closed shapes directly
2. reconstructs additional footprints from connectivity
3. filters them by family-relevant geometry
4. preserves source provenance so the output stays explainable

## Current Limits

The current solver does not fully handle:

- `HATCH` boundary extraction as first-class polygons
- `INSERT` explosion
- `SPLINE`
- exact bulge handling for all polyline curvature
- second-pass merge logic for fragmented wall runs
- explicit glazing-grid recovery

Those are natural next steps, not hidden assumptions.

## Repo Structure

- [`tokenize_dxf.py`](tokenize_dxf.py): minimal submission entry point
- [`augrade/`](augrade/): package implementation
- [`augrade/cli/`](augrade/cli/): CLI shims
- [`reference/`](reference/): process, research, and experiment docs
- [`out/`](out/): canonical generated bundle

## Bottom Line

This repo should be read in two layers:

### Submission-facing

- transparent geometry-first solver
- reproducible outputs
- visual verification

### Supplementary

- provenance and normalization analysis
- dashboard and merge-lab review tools
- annotation path for future learned merge / graph work

The core claim is simple:

> I solved the take-home with a transparent geometric pipeline, and I used provenance-aware analysis to understand drafting variation without mistaking it for structural truth.
