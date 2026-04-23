# Research Extension

This note holds the broader GenAI research framing behind the runnable
DXF solver. It is intentionally separate from
[`thesis.md`](thesis.md), which stays reviewer-facing and evidence-first.

The short version: the solver exposes a stable deterministic geometry
layer under authored drafting variation. The research opportunity is to
learn the residual review and merge decisions while preserving that
layer's closure, typing, and provenance guarantees.

## Framing: Structured Representation Alignment

The framing that fits this problem most closely is **structured
representation alignment**: a useful representation must do two things
at once.

- **Cross-domain alignment:** pull together views that describe the same
  underlying object despite surface differences.
- **Domain discernibility:** preserve which source the view came from,
  so the system can know when to trust or distrust it.

That is exactly the move this repo makes at the drafting level.

- Different layer variants, carrier choices, and decomposition
  conventions are different domains.
- The geometric pipeline aligns them when they describe the same
  underlying element.
- The system still preserves provenance through `source_layers`,
  `source_kind`, layer normalization analysis, and merge labels.

The practical principle used elsewhere in the repo is:

> pool for geometry, tag for provenance

This is also why HATCH should be handled differently at ingestion and
provenance time, but not downstream as a second geometric core. Once an
outer boundary has become a valid clockwise polygon, the rest of the
stack can consume it through the same polygon abstraction.

## Grammar And Composition

At the DXF level, "grammar learning" is not a metaphor for adding a
large model early. It means making the authored rewrite rules explicit:
which primitive carriers can form closed tokens, which layer variants
pool into the same family, which provenance fields must remain visible,
and which pair relations are candidates for merge or review.

The co-design reference that best matches this direction is Cai et al.
2026, not the older Censi paper as the lead citation. Censi gives the
foundational monotone co-design formalism; Cai et al. isolate a tractable
linear/polyhedral subclass and emphasize closure under interconnection
plus exact scalable computation. That is closer to the claim here: build
a compositional scaffold whose local pieces can be connected without
losing the guarantees that make review possible.

## Operational Test: Inner-Product Geometry

"Structured representation alignment" is the frame, but the operational
question is:

> what representation makes compatible merges close and incompatible
> merges far under the drafting-rewrite symmetries the file actually
> exhibits?

The relevant symmetries here are not camera or viewpoint transforms.
They are authored rewrites such as:

- split or merge collinear segments
- swap direct-vs-graph-face carriers
- perturb the snap lattice within a tolerance class
- remap between companion layer schemas
- express a filled region as HATCH boundary topology instead of outline
  linework

Geometric-equivariance work such as GATr is a useful reference point
because it makes representation choice central: choose a space where the
query becomes simple under the relevant symmetries. That literature
usually studies Lie-group actions on Euclidean coordinates. Drafting
rewrites are not clean Lie-group actions; they are categorical
equivalences induced by authoring convention. The vocabulary and
training recipes transfer; the theorems do not directly apply.

The operational form for this problem is therefore: rewrite-invariance
is a candidate inductive bias for any future learned scorer, and the
mechanism should be tested rather than assumed.

Three mechanisms are worth comparing:

- **Explicit invariance penalty.** Add an auxiliary loss over generated
  rewrite pairs. Auditable; the loss value reads directly as "how
  invariant is the scorer?"
- **Augmentation along rewrite orbits.** Train on equivalent views
  without a separate penalty. Simpler to implement; invariance is less
  directly measurable.
- **Architectural symmetry-breaking inputs.** ASEN-style auxiliary
  inputs can select an effective subgroup per instance. This is
  interesting but risky here: if provenance features become the
  symmetry-breaking input, semantic equivalence becomes parameterized by
  provenance, which cuts against "pool for geometry, tag for provenance."

The first two mechanisms are compatible with the current merge lab. The
third is a structural commitment that would need its own justification.

## The Stack

This project sits at the bottom of a longer review-and-learning system:

```text
Layer 1: Geometric perception (primitives -> endpoints)           <- current solver
Layer 2: Object formation / tokenization (endpoints -> polygons)  <- current solver
Layer 3: Graph construction (polygons -> typed relationships)
Layer 4: Pair-relation scoring
Layer 5: Prototype / memory head
Layer 6: GNN consistency propagation
Layer 7: Structured readout / validator interface
Layer 8: Validator loop
```

The entropy split is explicit:

| Entropy profile | What belongs here |
|---|---|
| deterministic geometry layer | closure, winding, validity, family priors, family geometric filters, rewrite-invariance constraints |
| adaptive review layer | tolerance selection under drafting style, pair-relation scoring, family-conditioned merge heads, prototype memory, reviewer feedback |

The solver tests the scaffold. The dashboard and merge lab expose the
next layer.

## Extension Plan

The research path should be staged so learned components are introduced
only where the deterministic scaffold leaves a real residual problem.

0. **Rewrite-invariance as a candidate training-time inductive bias.**
   Generate equivalent views of the same merge relation using rewrite
   generators: collinear split/merge, carrier swap, snap-lattice
   perturbation, schema remap, and HATCH-vs-outline carrier changes.
   Compare explicit invariance penalties, orbit-based augmentation, and
   symmetry-breaking auxiliary inputs.
1. **Label candidate pairs through the merge lab.** Keep family,
   source-kind, canonical-layer, gap, overlap, and bbox relation visible
   to the reviewer.
2. **Train sparse edge scorers on pair features, with calibrated
   uncertainty.** Conformal prediction is the natural calibration tool:
   the problem has drafter-style shift, small clean labels, and a need
   to distinguish "auto-merge" from "show a reviewer."
3. **Add prototype memory in the small-clean-label regime.** Dense
   associative memory with compositional hidden encoding is a plausible
   fit for pair-feature prototypes, where the system needs reusable
   merge patterns without collapsing everything into nearest-neighbor
   buckets.
4. **Add a GNN only as consistency propagation across already-scored
   pair relations.** 2-closure as edge features is a tractable handle
   for subgroup-style equivariance inside ordinary graph backbones.
5. **Emit typed edit proposals and structured readouts.** The end
   product should be validator-facing: explicit proposed merges,
   uncertainty bands, provenance, and counterexamples.

The GNN is not the first step. It is what comes after the quotient is
reasonably right. The point of the scaffold is to prevent the project
from collapsing into brittle edge-case patching before the scalable
representation is defined.

## Concrete Backing

This direction is anchored in repo artifacts:

- [`thesis.md`](thesis.md) gives the short file-backed claims.
- [`programmatic_vs_contextual_merges.md`](programmatic_vs_contextual_merges.md)
  documents the two-quotient split with per-family evidence.
- [`../experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](../experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md)
  sharpens the quotient hypothesis.
- [`../experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](../experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md)
  turns the hypothesis into phases 0-8.
- [`../process/layer_normalization_analysis.md`](../process/layer_normalization_analysis.md)
  supplies the layer-schema evidence behind cross-layer pooling.

## References

### Structured representation and co-training

- Yu Lei, Minghuan Liu, Abhiram Maddukuri, Zhenyu Jiang, Yuke Zhu,
  *A Mechanistic Analysis of Sim-and-Real Co-Training in Generative
  Robot Policies*, 2026. [`arXiv:2604.13645`](https://arxiv.org/abs/2604.13645)

### Operational test / equivariance

- Johann Brehmer, Pim de Haan, Sonke Behrends, Taco Cohen,
  *Geometric Algebra Transformer*, 2023. [`arXiv:2305.18415`](https://arxiv.org/abs/2305.18415)
- Pim de Haan, Taco Cohen, Johann Brehmer, *Euclidean, Projective,
  Conformal: Choosing a Geometric Algebra for Equivariant Transformers*,
  AISTATS / PMLR 238, 2024. [`PMLR`](https://proceedings.mlr.press/v238/haan24a.html)
- Michael M. Bronstein, Joan Bruna, Taco Cohen, Petar Velickovic,
  *Geometric Deep Learning: Grids, Groups, Graphs, Geodesics, and
  Gauges*, 2021. [`arXiv:2104.13478`](https://arxiv.org/abs/2104.13478)
- Abhinav Goel, Derek Lim, Hannah Lawrence, Stefanie Jegelka, Ningyuan
  Huang, *Any-Subgroup Equivariant Networks via Symmetry Breaking*,
  ICLR 2026. [`OpenReview`](https://openreview.net/forum?id=jz3d7nvtGz);
  [`arXiv:2603.19486`](https://arxiv.org/abs/2603.19486)

### Compositionality / co-design

- Yubo Cai, Yujun Huang, Meshal Alharbi, Gioele Zardini, *Scalable
  Co-Design via Linear Design Problems: Compositional Theory and
  Algorithms*, 2026. [`arXiv:2603.29083`](https://arxiv.org/abs/2603.29083)
- Andrea Censi, *A Mathematical Theory of Co-Design*, 2015. Foundational
  monotone co-design background for the 2026 linear co-design framing.
  [`arXiv:1512.08055`](https://arxiv.org/abs/1512.08055)

### Scoring / calibration / memory

- Vladimir Vovk, Alexander Gammerman, Glenn Shafer, *Algorithmic
  Learning in a Random World*, 2005 / 2022.
- Goodfire, *Explaining 4.2 million genetic variants with
  state-of-the-art, interpretable predictions*, 2026. Industry research
  resource; cite as a resource rather than an arXiv paper.
  [`Goodfire EVEE`](https://www.goodfire.ai/research/evee-explaining-genetic-variants)
- Mohadeseh Shafiei Kafraj, Dmitry Krotov, Peter E. Latham, *A
  Biologically Plausible Dense Associative Memory with Exponential
  Capacity*, 2026. [`arXiv:2601.00984`](https://arxiv.org/abs/2601.00984)
