# DXF Primitive-to-Polygon Reconstruction

Airport mezzanine DXF: ~67,000 primitives across ~111 layers, no
grouping metadata, recover closed polygons grouped by element type.

The solver targets scoped wall, column, and curtain-wall layers; JSON
with `walls`, `columns`, `curtain_walls`, and `metrics`; clockwise
closed rings; SVG overlays for review; and warnings when scoped layers
are missing. `HATCH` is a first-class primitive in DXF; companion
`* HATCH` layers (fill vs outline on separate layers) are included in
scope and contribute `direct_hatch` polygons where outer boundary paths
parse.

The approach is geometry-first:

- parse the DXF into primitive carriers
- extract already-closed carriers directly
- flatten open linework into a snapped endpoint graph
- walk bounded faces on the resulting planar graph
- filter faces by family-relevant geometry
- preserve `source_layers` so every polygon stays traceable

## Run

```bash
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out
```

Stdlib-only. No install step. The flagless run is the default
configuration (snap = 0.5) and matches the checked-in `out/` bundle.

The result on the supplied file:

| walls | columns | curtain walls | coverage |
| --- | --- | --- | --- |
| 1158 | 764 | 304 | 51.4% |

Coverage is reported as a source-entity-length proxy; it is not the
grader's exact primitive-inside-polygon coverage calculation.

Outputs written to `out/`:

- `tokenization_output.json` — deliverable JSON (polygons per family, `source_layers`, `vertices`)
- `analysis_summary.json` — runtime, entity counts, family primitive counts, snap-tolerance sweep, direct-vs-graph-face split, coverage proxy, the resolved mode + snap-tolerance
- `analysis_report.md` — short human-readable version
- `raw_all.svg`, `raw_target_families.svg`, `extracted_overlay.svg`, `walls.svg`, `columns.svg`, `curtain_walls.svg`, `wall_connectivity_snap_<tol>.svg`

## How To Read This Repo

Three layers, in this order:

### 1. Direct Solver

Start here for the direct polygon-reconstruction path.

- [`tokenize_dxf.py`](tokenize_dxf.py) — stdlib parser + extractor (single file)
- [`DESIGN.md`](DESIGN.md) — one-page approach + per-family strategy + failure modes
- [`out/tokenization_output.json`](out/tokenization_output.json) — deliverable JSON
- [`out/extracted_overlay.svg`](out/extracted_overlay.svg) — visual verification

### 2. Supplementary Analysis

Read this if you want to understand the artifact beyond the count.

- [`reference/process/layer_normalization_analysis.md`](reference/process/layer_normalization_analysis.md) — why `FAMILY_LAYER_MAP` pools the hyphen/space variants
- [`reference/research/programmatic_vs_contextual_merges.md`](reference/research/programmatic_vs_contextual_merges.md) — the two-stage merge decomposition with per-family evidence
- `agent_merge_review.py` + `agent_labels.json` — programmatic labelling of 87 merge candidates (run it; it produces the labels)
- `python -m augrade.cli.pipeline` — regenerates dashboard + merge lab on demand (not tracked)

This layer is about provenance, drafting variation, merge ambiguity,
and reviewability. It supports audit and annotation; it is not the
primary output.

### 3. Research Direction

Read this if you want the bridge from this geometric scaffold to a
learned review system.

- [`reference/research/thesis.md`](reference/research/thesis.md) — short, evidence-first thesis grounded in this file
- [`reference/research/research_extension.md`](reference/research/research_extension.md) — broader GenAI research framing and staged extension plan
- [`reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md) — the merge-relation hypothesis sharpened
- [`reference/experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](reference/experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md) — phases 0–8

The geometric solver in layer 1 is the runnable artifact. Later layers
are documented as future work, not part of the current solver.

## Parameter Notes

The default result uses snap tolerance `0.5`. After
HATCH extraction, snap tolerance mainly affects graph-face recovery
around the direct carriers. More aggressive tolerances can add or
reshuffle graph faces, but the coverage gain is marginal compared with
the higher merge risk.

### Advanced override: `--snap-tolerance`

For experiments, `--snap-tolerance` overrides `--mode` and accepts:

```bash
# scalar, uniform across all families
--snap-tolerance 0.5

# per-family map (unspecified families fall back to the mean of provided values)
--snap-tolerance walls=0.5,columns=0.25,curtain_walls=0.35

# adaptive: choose from a small wall-connectivity preset sweep
--snap-tolerance adaptive
```

The adaptive mode chooses from `[0.1, 0.25, 0.5, 1.0]` using a simple
wall-connectivity score; on this file it returns `0.5`, matching the
default. This is an advanced surface, not the default path.

## Library, REPL, and review surfaces

The same extraction is packaged so the dashboard, merge lab, REPL, and
agent-review script all consume one `AnalysisDataset`:

```bash
# full review bundle (regenerates dashboard + merge lab; none tracked)
python3 -m augrade.cli.pipeline "Airport Doors_MEZZ.dxf" out_bundle
python3 scripts/verify_dashboards.py --bundle out_bundle
python3 scripts/verify_regions.py --bundle out_bundle

# interactive workbench
python3 -m augrade.repl --input "Airport Doors_MEZZ.dxf" --output out_bundle

# programmatic merge review using the library
python3 agent_merge_review.py "Airport Doors_MEZZ.dxf"
```

The library exists to make the extraction reusable; it is optional, not
required for the direct solver. Review surfaces live in [`augrade/review/`](augrade/review/)
as a subpackage so `augrade/extract.py`, `augrade/geometry.py`,
`augrade/dataset.py`, `augrade/merge.py`, and `augrade/provenance.py`
can be read without paging through ~2500 lines of HTML generator. The
generated HTML/JSON dumps (`dashboard.html`, `merge_lab.html`,
`merge_lab_data.json`, `dashboard_assets/`, `provenance_index.json`,
`pipeline_manifest.json`) are gitignored — regenerate via the
pipeline command above. The screenshot verification scripts are optional
QA helpers and require Playwright.

## What the analysis found

The file is not geometry plus random noise. It is authored variation
over a stable object structure: layer-schema differences, carrier
differences (`LINE` vs `LWPOLYLINE` vs `HATCH` vs `CIRCLE`),
decomposition differences, drafting-zone differences. Three concrete
findings fed back into the solver's defaults:

1. **Cross-layer pooling is real.** `A-GLAZING MULLION` (`LINE`-only)
   and `A-GLAZING-MULLION` (`LWPOLYLINE`-only) are the same physical
   mullions drawn with different CAD conventions, ~97% spatial
   overlap. That is why `FAMILY_LAYER_MAP["curtain_walls"]` pools both.

2. **Merges factor into two stages.** A programmatic stage is
   decidable from provenance alone (same `canonical_layer` + gap ≈ 0
   + different `source_kind`), followed by a contextual stage that needs
   neighborhood reasoning. On this file 29/29 curtain-wall merges are
   programmatic; only 1/28 wall merges are.

3. **Snap tolerance has a validated default.** The wall-family
   connectivity sweep selects 0.5, which is the default.

The principle tying these together is **"pool for geometry, tag for
provenance"** — use layer variants and carrier choices together for
geometry, but keep enough provenance to audit every polygon. The short
evidence-first thesis lives in
[`reference/research/thesis.md`](reference/research/thesis.md), with the
broader research extension separated into
[`reference/research/research_extension.md`](reference/research/research_extension.md).

## Current limits

Not yet handled:

- arbitrary `HATCH` on non-scoped layers (only scoped family layers are read)
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
requirements.txt                      stdlib note (+ optional ezdxf for two library modules)
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
  review/                             isolated review UI: dashboard, merge lab, labels

reference/
  research/thesis.md                  evidence-first thesis
  research/research_extension.md      broader research framing
  research/programmatic_vs_contextual_merges.md
  process/layer_normalization_analysis.md
  experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md
  experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md

out/                                  default generated bundle (SVGs + JSON + report)
```

## Summary

A single stdlib command produces the required polygons. The library, REPL,
and isolated review subpackage are optional review tools. The default
tolerance and pooling choices are defended by concrete findings in the
reference docs, not chosen by hand.
