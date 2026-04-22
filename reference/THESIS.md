# Thesis

Consolidated from the pre-task material (`research_doc.md`, `bigger_picture.md`, `implementation_outline.md`) and the findings that survived contact with the file.

## The Task

**Input.** ~67,000 DXF primitives (`LINE`, `ARC`, `LWPOLYLINE`, `CIRCLE`, `ELLIPSE`, `HATCH`, `POLYLINE`) across ~111 layers, with no grouping metadata. A "wall" exists only as disconnected segments that a human perceives as belonging together.

**Output.** Closed polygons grouped by element type — walls, columns, curtain walls — each tagged with the raw drafting layers it was recovered from.

**Difficulty.** The object-level footprint is not in the file; it has to be reconstructed from primitive-level drafting work. The variability is not sensor noise — it is authored choice about layer schema, carrier type (`LINE` vs `LWPOLYLINE` vs `HATCH` vs `CIRCLE`), decomposition granularity, and local junction policy.

## The Approach

Treat the file as a tokenization problem over geometry:

| Grammar-induction concept | DXF implementation |
| --- | --- |
| characters | primitives |
| closure rules | endpoints connect, CW winding |
| tokens | closed polygons |
| typed semantics | family inference from layer priors + family-relevant geometric filters |
| residual metadata | `source_layers` attached to every polygon |

The algorithm is deliberately low-entropy: extract already-closed carriers directly, flatten the rest into segments, snap endpoints, walk bounded faces on the resulting planar graph, keep the faces that pass family-specific aspect/area/compactness filters, preserve provenance. No learned components; no hidden assumptions.

## Framing: Structured Representation Alignment

The language that matches this problem most precisely comes from the co-training literature ([science-of-co-training.github.io][1]). The central finding there is that useful learning from heterogeneous sources requires *structured representation alignment* — a balance between two pressures:

- **cross-domain alignment**: pull together samples that describe the same underlying object despite surface differences
- **domain discernibility**: do not erase which source a sample came from; preserve the signal that lets the system know when to trust or distrust a view

That is precisely the move this repo makes at the geometry level. Each drafting-layer variant, carrier choice, and decomposition convention is a "domain" producing a different view of the same architectural element. The right representation:

- **aligns** those views at the semantic level — a circle and a faceted polyline describing the same column collapse to one polygon, the hyphen/space variant `A-GLAZING MULLION` / `A-GLAZING-MULLION` pool into one family
- **preserves domain discernibility** — `source_layers` stays on every polygon, the carrier kind (`direct_*` vs `graph_face`) is reported in `analysis_summary.json.graph_vs_direct_counts`, and the normalization side of the augrade package records the full raw-layer → canonical-layer table as a residual.

The slogan the rest of the docs use for this is **"pool for geometry, tag for provenance"**. It is the same claim as structured representation alignment, applied to authored drafting rewrites instead of the sim-to-real domain gap.

The consequence for the architecture is that alignment pressure belongs *at the geometry level* (pooling layer variants, snap-equivalencing nearby endpoints, merging complementary outline/hatch carriers), while discernibility pressure belongs *at the provenance level* (keep the raw layer name, keep the carrier kind, keep the variant group). Blind alignment that collapses provenance is the canonical failure mode — it produces the same failure the co-training paper calls negative transfer.

## The Stack

This task sits at Layers 1–2 of a longer architecture:

```
Layer 1: Geometric Perception (primitives → endpoints)           ← THIS TASK
Layer 2: Object Formation / Tokenization (endpoints → polygons)  ← THIS TASK
Layer 3: Graph Construction (polygons → typed relationships)
Layer 4: Pair-Relation Scoring (continuation, duplication, grouping)
Layer 5: Prototype / Memory Head (expert labels, small-data regime)
Layer 6: GNN Consistency Propagation
Layer 7: Validator Loop (building codes, physics)
```

The entropy split across layers is explicit:

| Entropy profile | What belongs here |
| --- | --- |
| **Low-entropy scaffold** | closure, winding, validity, family layer priors, family-specific geometric filters — stable across files, safe to hand-code |
| **High-entropy adaptation** | tolerance selection under drafter-specific style, pair-relation scoring, family-conditioned merge heads, reviewer feedback |

The take-home is a clean test of the scaffold. The merge lab on the derivative branch is the scaffold's first feedback surface into the adaptation layer.

## What The File Actually Contains

The empirical findings the repo is built on:

**Normalization.** `A-GLAZING MULLION` is `LINE` only; `A-GLAZING-MULLION` is `LWPOLYLINE` only; together they cover 97% of the same spatial region. These are the same physical mullions drawn with two CAD conventions. `A-GLAZING FULL` and `A-GLAZING-FULL` have similar names but mostly disjoint spatial regions, so name-normalization alone is wrong — spatial overlap and entity-type profiles have to be checked. See [`process/layer_normalization_analysis.md`](process/layer_normalization_analysis.md).

**Programmatic vs contextual merges.** The merge problem factors into two sequential quotients — a programmatic one that's decidable from provenance metadata alone (same `canonical_layer` + `boundary_gap ≈ 0` + `source_kind` disagreement) and a contextual one that requires neighborhood reasoning. 29/29 curtain-wall merges on this file are programmatic; only 1/28 wall merges are. See [`research/programmatic_vs_contextual_merges.md`](research/programmatic_vs_contextual_merges.md).

**Family-typed structure.** Columns behave like a duplicate-overlap problem (IoU is often substantial, gaps are small). Walls behave like a continuity-and-compatibility problem (IoU near zero, angle differences broad). Curtain walls behave like a grid-lattice problem (area ratios near one, minor-gap as the separator). This is why the merge layer is family-typed rather than monolithic.

## The Extension Plan

Sketched in [`experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md) and operationalized in [`experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md). The order is deliberate:

1. **Label candidate pairs** through the merge lab (positives + negatives, oversample the decision boundary).
2. **Sparse edge scorer** on pair features — linear, then tree.
3. **Prototype memory** (Hopfield-style margin) using the expert labels. Appropriate to the small-clean-label regime; avoids training a big embedding before the quotient structure is established.
4. **GNN over the candidate graph** only as consistency propagation across already-scored pair relations — not as the primary representation.
5. **Rewrite-invariance tests**: generate equivalent views of the same relation (split/merge collinear segments, swap direct-vs-graph-face carriers, perturb the snap lattice, remap between companion layer schemas) and require the learned state to be stable under them.

The working hypothesis: *merge-relevant architectural cleanup factors through a small typed quotient over pair relations between polygon candidates, with provenance retained as a residual side channel.* That is the structured-representation-alignment claim, stated in the problem's native vocabulary.

## What The Take-Home Proved Empirically

- A geometry-first pipeline produces 274 / 572 / 304 walls / columns / curtain walls on the supplied file in ~4s with stdlib-only code, consuming 19.9% of scoped-layer drawable length.
- The hyphen/space layer variants collapse programmatically; 29 curtain-wall merges come essentially for free from the quotient.
- Column merges split into interpretable buckets — extraction dedup (same layer, gap ≈ 0, different carrier), distinct-but-close (same layer, gap 0.2–1.0, need spatial context), and ambiguous. 87 auto-labels across all three families were generated by `agent_merge_review.py` with zero visual inspection.
- Snap tolerance is not a magic number — the wall-family degree-4+ histogram has a discernible elbow around 0.5 on this file, and the adaptive mode picks that elbow automatically (`pick_adaptive_tolerance` in `tokenize_dxf.py`).
- The same core extraction function (`extract_faces_from_segments`) supports uniform, per-family, and adaptive snap without architectural change — family partitioning was already present inside the loop.

## Reading Order

For an interview conversation:

1. `DESIGN.md` — one-page approach + failure modes.
2. This document — the framing and the extension plan.
3. `process/layer_normalization_analysis.md` — the most concrete evidence for the quotient/residual split.
4. `research/programmatic_vs_contextual_merges.md` — the two-quotient decomposition with per-family counts.
5. `experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md` — where the representation claim gets sharp.

## References

[1]: https://science-of-co-training.github.io/ "Science of Co-Training — structured representation alignment"

- Lei et al., *A Mechanistic Analysis of Sim-and-Real Co-Training in Generative Robot Policies*, 2026. Introduces the structured-representation-alignment-plus-domain-discernibility decomposition used as framing above.
- The *Representational Alignment (Re²-Align)* workshop series at ICLR 2024/2025/2026 for the broader program.
