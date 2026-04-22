# DXF Primitive-to-Polygon Reconstruction

Airport mezzanine take-home: ~67,000 DXF primitives across ~111 layers,
no grouping metadata, recover closed polygons grouped by element type.

The approach is a geometry-first tokenizer:

- parse the DXF into primitive carriers
- extract already-closed carriers directly
- flatten open linework into a snapped endpoint graph
- walk bounded faces on the resulting planar graph
- filter faces by family-relevant geometry
- preserve `source_layers` so every polygon stays traceable

The slogan for why provenance survives is **"pool for geometry, tag for
provenance"** — align cross-domain views (layer variants, carrier
choices, decomposition conventions) at the semantic level, preserve
domain discernibility as a residual side channel. That's the same
shape as *structured representation alignment* in the co-training
literature, applied to authored drafting rewrites rather than the
sim-to-real gap. See [`reference/THESIS.md`](reference/THESIS.md).

## Run

Stdlib-only solver:

```bash
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out
```

The snap tolerance is unified behind one argument:

```bash
# scalar, uniform across all families (default 0.5)
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out --snap-tolerance 0.5

# per-family (unspecified families fall back to the mean of provided values)
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out \
    --snap-tolerance walls=0.5,columns=0.25,curtain_walls=0.35

# adaptive: elbow of the wall-family degree-4+ histogram, applied uniformly
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out --snap-tolerance adaptive
```

The solver writes, to `out/`:

- `tokenization_output.json` — graded output (polygons per family, `source_layers`, `vertices`)
- `analysis_summary.json` — runtime, entity counts, family primitive counts, snap-tolerance sweep, direct-vs-graph-face split, coverage proxy, the resolved snap-tolerance value
- `analysis_report.md` — short human-readable version
- `raw_all.svg`, `raw_target_families.svg`, `extracted_overlay.svg`, `walls.svg`, `columns.svg`, `curtain_walls.svg`, `wall_connectivity_snap_0_5.svg`

Result on the supplied file: **274 walls, 572 columns, 304 curtain
walls** in ~4 seconds, consuming ~19.9% of scoped-layer drawable
length. Reproducible from the command above.

## Library, REPL, and review surfaces

The same extraction is packaged as a library so the dashboard, merge
lab, REPL, and agent-review script all consume one `AnalysisDataset`:

```bash
# full HITL bundle (regenerates dashboard + merge lab, none tracked by git)
python3 -m augrade.cli.pipeline "Airport Doors_MEZZ.dxf" out_bundle

# interactive workbench
python3 -m augrade.repl --input "Airport Doors_MEZZ.dxf" --output out_bundle

# programmatic merge review using the library (produces agent_labels.json)
python3 agent_merge_review.py "Airport Doors_MEZZ.dxf"
```

The library refactor was the point — it let `tokenize_dxf.py` stay a
tight stdlib file while giving every surface (dashboard, merge lab,
REPL, agent script) a shared data model.

Review surfaces live in [`augrade/review/`](augrade/review/) as a
subpackage, isolated from the core so you can read `augrade/extract.py`,
`augrade/geometry.py`, `augrade/dataset.py`, `augrade/merge.py`, and
`augrade/provenance.py` without paging through ~2500 lines of HTML
generator. The generated artifacts (`dashboard.html`, `merge_lab.html`,
`merge_lab_data.json`, `dashboard_assets/`, `provenance_index.json`,
`pipeline_manifest.json`) are gitignored — regenerate via the pipeline
command above.

## What the analysis found

The file is not geometry plus random noise. It's authored variation
over a stable object structure: layer-schema differences, carrier
differences (`LINE` vs `LWPOLYLINE` vs `HATCH` vs `CIRCLE`),
decomposition differences, drafting-zone differences.

Three concrete findings from the analysis fed back into the solver's
defaults:

1. **Cross-layer pooling is real.** `A-GLAZING MULLION` (`LINE`-only) and
   `A-GLAZING-MULLION` (`LWPOLYLINE`-only) are the same physical mullions
   drawn with different CAD conventions, 97% spatial overlap. That's
   why `FAMILY_LAYER_MAP["curtain_walls"]` pools both. See
   [`reference/process/layer_normalization_analysis.md`](reference/process/layer_normalization_analysis.md).

2. **Merges factor into two quotients.** A programmatic quotient
   decidable from provenance alone (same `canonical_layer` + gap ≈ 0
   + different `source_kind`) and a contextual quotient that needs
   neighborhood reasoning. 29/29 curtain-wall merges on this file
   are programmatic; only 1/28 wall merges are. See
   [`reference/research/programmatic_vs_contextual_merges.md`](reference/research/programmatic_vs_contextual_merges.md).

3. **Snap tolerance is family-typed in the limit.** The wall-family
   degree-4+ histogram has a discernible elbow around 0.5 on this
   file. Columns want a tighter snap (fewer distinct corners to
   merge); curtain walls want something in between. `--snap-tolerance`
   accepts all three modes for this reason.

## Extension direction

The solver is Layer 1–2 of a longer stack; the remaining layers are
staged in [`reference/THESIS.md`](reference/THESIS.md) and the two
experiment docs. The short version:

1. Label candidate pairs (positives + negatives) through the merge lab.
2. Sparse edge scorer on pair features — linear, then tree.
3. Prototype memory (Hopfield-style margin) on expert labels.
4. GNN only as consistency propagation across already-scored pair
   relations, not as the primary representation.
5. Rewrite-invariance tests: generate equivalent views of the same
   relation (split/merge collinear segments, swap direct-vs-graph-face
   carriers, perturb the snap lattice, remap between companion
   layers) and require the learned state to be stable.

## How to explain this to a structural engineer

- A DXF doesn't store semantic wall or column objects, it stores
  drafting primitives.
- The task is to reconstruct the closed footprints a human would
  recognize as elements.
- Columns are easiest (many are already circles or compact outlines).
- Curtain walls are regular local panel footprints.
- Walls are hardest because they're mostly fragmented linework with
  high-degree junctions.
- The algorithm takes the obvious closed shapes, reconstructs the
  rest from connectivity, filters by family geometry, and preserves
  source provenance.

## Current limits

Not yet handled:

- `HATCH` boundary extraction as first-class polygons
- `INSERT` explosion
- `SPLINE`
- exact bulge for all polyline curvature
- second-pass merge for fragmented wall runs (deferred to the learned layer)
- explicit glazing-grid recovery (likewise)

These are the natural next steps, not hidden assumptions.

## Repo layout

```
tokenize_dxf.py                       stdlib solver (reviewer entry point)
DESIGN.md                             one-page approach + failure modes
README.md                             this file
requirements.txt                      stdlib note (+ ezdxf for the library-side)
agent_merge_review.py                 programmatic merge review via the library
agent_labels.json                     87 auto-labels produced by the above

augrade/                              library and review surfaces
  __init__.py
  extract.py                          ExtractionResult facade
  geometry.py                         geometric helpers
  dataset.py                          AnalysisDataset (shared compute)
  merge.py                            FAMILY_PRESETS, pair scoring
  provenance.py                       raw-layer table + variant groups
  normalize.py                        layer-schema anomaly detection
  emit_dxf.py                         cleaned-DXF output (optional)
  pipeline.py                         one-shot full bundle
  repl.py                             interactive workbench
  cli/                                thin CLI shims
  review/                             isolated HITL: dashboard, merge lab, labels

reference/
  THESIS.md                           framing + extension plan (read first)
  process/layer_normalization_analysis.md
  research/programmatic_vs_contextual_merges.md
  experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md
  experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md

out/                                  canonical generated bundle (SVGs + JSON + report)
```

## Bottom line

A transparent geometric pipeline run by a single stdlib command
produces the graded polygons; a library + REPL + review subpackage
sit next to it for the HITL loop that the extension plan depends on;
the reference docs frame the whole thing as structured representation
alignment and lay out what the next layers of the stack look like.
The defaults, pooling choices, and `--snap-tolerance` modes in the
solver are defended by the findings in the reference docs, not chosen
by hand.
