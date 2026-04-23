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

## Run

```bash
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out
```

Stdlib-only. No install step. Default is `--mode conservative`
(snap = 0.5), which is the documented baseline and matches the
canonical `out/` bundle in this repo.

The result on the supplied file:

| mode | walls | columns | curtain walls | coverage |
| --- | --- | --- | --- | --- |
| conservative (default) | 274 | 572 | 304 | 19.9% |
| liberal | 288 | 568 | 309 | 20.8% |

Outputs written to `out/`:

- `tokenization_output.json` — graded output (polygons per family, `source_layers`, `vertices`)
- `analysis_summary.json` — runtime, entity counts, family primitive counts, snap-tolerance sweep, direct-vs-graph-face split, coverage proxy, the resolved mode + snap-tolerance
- `analysis_report.md` — short human-readable version
- `raw_all.svg`, `raw_target_families.svg`, `extracted_overlay.svg`, `walls.svg`, `columns.svg`, `curtain_walls.svg`, `wall_connectivity_snap_<tol>.svg`

## How To Read This Repo

Three layers, in this order:

### 1. Direct Solver

Start here for the take-home answer.

- [`tokenize_dxf.py`](tokenize_dxf.py) — stdlib parser + extractor (single file)
- [`DESIGN.md`](DESIGN.md) — one-page approach + per-family strategy + failure modes
- [`out/tokenization_output.json`](out/tokenization_output.json) — graded output
- [`out/extracted_overlay.svg`](out/extracted_overlay.svg) — visual verification

### 2. Supplementary Analysis

Read this if you want to understand the artifact beyond the count.

- [`reference/process/layer_normalization_analysis.md`](reference/process/layer_normalization_analysis.md) — why `FAMILY_LAYER_MAP` pools the hyphen/space variants
- [`reference/research/programmatic_vs_contextual_merges.md`](reference/research/programmatic_vs_contextual_merges.md) — the two-quotient decomposition with per-family evidence
- `agent_merge_review.py` + `agent_labels.json` — programmatic labelling of 87 merge candidates (run it; it produces the labels)
- `python -m augrade.cli.pipeline` — regenerates dashboard + merge lab on demand (not tracked)

This layer is about provenance, drafting variation, merge ambiguity,
and reviewability. It supports audit and annotation; it is not the
graded output.

### 3. Future ML Framing

Read this if you want the bridge from the take-home to a learned system.

- [`reference/research/thesis.md`](reference/research/thesis.md) — structured representation alignment, the seven-layer stack, the extension plan
- [`reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md) — the quotient claim sharpened
- [`reference/experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](reference/experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md) — phases 0–8

The geometric solver in layer 1 is a preliminary scaffold. Layers 4+
are deliberately not built into the take-home; they are sketched as
the path forward, not pretended into the artifact.

## Operating Modes

Two named modes cover the operating story; they map to a single snap
tolerance applied uniformly.

| Mode | Snap | When to use |
| --- | --- | --- |
| `conservative` (default) | 0.5 | Submission / audit / canonical bundle |
| `liberal` | 0.75 | Slightly wider snap; recovers a few more candidates with mild over-merging |

```bash
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out --mode conservative
python3 tokenize_dxf.py "Airport Doors_MEZZ.dxf" out --mode liberal
```

`0.75` is chosen because `1.0`, `1.5`, and `2.0` distort family counts
more aggressively (especially columns and curtain walls) for only a
marginal coverage gain.

### Advanced override: `--snap-tolerance`

For experiments, `--snap-tolerance` overrides `--mode` and accepts:

```bash
# scalar, uniform across all families
--snap-tolerance 0.5

# per-family map (unspecified families fall back to the mean of provided values)
--snap-tolerance walls=0.5,columns=0.25,curtain_walls=0.35

# adaptive: elbow of the wall-family degree-4+ histogram, applied uniformly
--snap-tolerance adaptive
```

The adaptive mode picks the elbow via the second-difference maximum
over `[0.1, 0.25, 0.5, 1.0]`; on this file it returns `0.5`,
matching `conservative`. This is an advanced surface, not the headline.

## Library, REPL, and review surfaces

The same extraction is packaged so the dashboard, merge lab, REPL, and
agent-review script all consume one `AnalysisDataset`:

```bash
# full HITL bundle (regenerates dashboard + merge lab; none tracked)
python3 -m augrade.cli.pipeline "Airport Doors_MEZZ.dxf" out_bundle --mode conservative

# interactive workbench
python3 -m augrade.repl --input "Airport Doors_MEZZ.dxf" --output out_bundle

# programmatic merge review using the library
python3 agent_merge_review.py "Airport Doors_MEZZ.dxf"
```

The library exists to make the extraction reusable — it is not the
main act. Review surfaces live in [`augrade/review/`](augrade/review/)
as a subpackage so `augrade/extract.py`, `augrade/geometry.py`,
`augrade/dataset.py`, `augrade/merge.py`, and `augrade/provenance.py`
can be read without paging through ~2500 lines of HTML generator. The
generated HTML/JSON dumps (`dashboard.html`, `merge_lab.html`,
`merge_lab_data.json`, `dashboard_assets/`, `provenance_index.json`,
`pipeline_manifest.json`) are gitignored — regenerate via the
pipeline command above.

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

2. **Merges factor into two quotients.** A programmatic quotient
   decidable from provenance alone (same `canonical_layer` + gap ≈ 0
   + different `source_kind`) and a contextual quotient that needs
   neighborhood reasoning. On this file 29/29 curtain-wall merges are
   programmatic; only 1/28 wall merges are.

3. **Snap tolerance has an elbow.** The wall-family degree-4+
   histogram has a discernible elbow around 0.5; `0.75` recovers a few
   more polygons at the cost of some merge precision. The two named
   modes encode this directly.

The slogan tying these together is **"pool for geometry, tag for
provenance"** — align cross-domain views (layer variants, carrier
choices, decomposition conventions) at the semantic level, preserve
domain discernibility as a residual side channel. That is the same
shape as *structured representation alignment* in the co-training
literature, applied to authored drafting rewrites rather than the
sim-to-real gap. Full framing in
[`reference/research/thesis.md`](reference/research/thesis.md).

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
  review/                             isolated HITL: dashboard, merge lab, labels

reference/
  research/thesis.md                  framing + extension plan
  research/programmatic_vs_contextual_merges.md
  process/layer_normalization_analysis.md
  experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md
  experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md

out/                                  canonical generated bundle (SVGs + JSON + report)
```

## Bottom line

A single stdlib command produces the graded polygons; a library, REPL,
and isolated review subpackage sit next to it for the HITL loop the
extension plan depends on; the reference docs frame the whole thing
as structured representation alignment and lay out what the next
layers of the stack look like. The defaults, pooling choices, and
mode names in the solver are defended by the findings in the
reference docs, not chosen by hand.
