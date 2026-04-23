# Chat Reference Bundle — Phase 1: Representation / Co-Training

This file collects the exact text to copy-paste into research-oriented chat threads. Phase 1 focuses on the representation/co-training framing: copy-whole primary docs first, followed by targeted excerpts.

---

## Copy whole — reference/research/thesis.md

Source: `reference/research/thesis.md`

# Thesis

Consolidated from the earlier research notes and the findings that survived contact with the file.

## Abstract

This project treats the DXF take-home as a structured representation problem rather than a bag-of-primitives cleanup exercise. Architectural drawings are authored with clean intent, so the right first move is to recover the low-entropy scaffold: closure, typed polygon formation, and provenance-preserving alignment across drafting variants. The direct solution here is geometric and reproducible: extract closed carriers, recover additional faces from a snapped endpoint graph, and retain `source_layers` as residual provenance. The exploratory work matters because it clarifies which irregularities are semantic and which are just authored representation choices. That same distinction defines the future ML substrate: pairwise merge relations, rewrite-invariant training objectives, and reviewer-facing annotation workflows. If the problem starts turning into brittle hand-negotiation with edge cases, that is a sign to move upward into scalable learned methods rather than keep hard-coding exceptions.

## The Task

**Input.** Roughly 67,000 DXF primitives (`LINE`, `ARC`, `LWPOLYLINE`, `CIRCLE`, `ELLIPSE`, `HATCH`, `POLYLINE`) across roughly 111 layers, with no grouping metadata. A wall or column is not stored as an object. It is only implied by drafting primitives that a human perceives as belonging together.

**Output.** Closed polygons grouped by element type:

- walls
- columns
- curtain walls

Each output polygon also retains the raw drafting layers it came from.

**Difficulty.** The object-level footprint is not in the file. It has to be reconstructed from primitive-level authoring work. The variability is not sensor noise. It is authored choice about:

- layer schema
- carrier type (`LINE`, `LWPOLYLINE`, `HATCH`, `CIRCLE`, ...)
- decomposition granularity
- local junction policy

## The Approach

Treat the DXF as a tokenization problem over geometry.

| Concept | DXF form |
|---|---|
| characters | primitives |
| closure rules | endpoints connect, CW winding |
| tokens | closed polygons |
| typed semantics | family inference from layer priors + family-relevant geometry |
| residual metadata | `source_layers` attached to every polygon |

The implementation is deliberately low-entropy:

- extract already-closed carriers directly
- flatten the rest into segments
- snap endpoints
- walk bounded faces on the resulting planar graph
- keep the faces that pass family-specific geometric filters
- preserve provenance

No learned components are required for the direct take-home solution.

## Framing: Structured Representation Alignment

The framing that fits this problem most closely is **structured representation alignment**: a useful representation must do two things at once.

- **cross-domain alignment**: pull together views that describe the same underlying object despite surface differences
- **domain discernibility**: preserve which source the view came from, so the system can know when to trust or distrust it

That is exactly the move this repo makes at the drafting level.

- Different layer variants, carrier choices, and decomposition conventions are different “domains.”
- The geometric pipeline aligns them when they describe the same underlying element.
- The system still preserves provenance through `source_layers`, `source_kind`, and layer/provenance analysis.

The practical slogan used elsewhere in the repo is:

> pool for geometry, tag for provenance

### Operational Test: Inner-Product Geometry

“Structured representation alignment” is the frame, but the operational question is:

> what representation makes compatible merges close and incompatible merges far under the drafting-rewrite symmetries the file actually exhibits?

The relevant symmetries here are not viewpoint transformations. They are authored rewrites such as:

- split/merge collinear segments
- swap direct-vs-graph-face carriers
- perturb the snap lattice within tolerance class
- remap between companion layer schemas

The right pair representation should make those equivalences cheap for the scorer.

That is why rewrite-invariance belongs in the **training objective** for any future learned scorer, not merely as a post-hoc validation test.

## The Stack

This take-home sits at the bottom of a longer system:

```text
Layer 1: Geometric Perception (primitives -> endpoints)           <- this task
Layer 2: Object Formation / Tokenization (endpoints -> polygons)  <- this task
Layer 3: Graph Construction (polygons -> typed relationships)
Layer 4: Pair-Relation Scoring
Layer 5: Prototype / Memory Head
Layer 6: GNN Consistency Propagation
Layer 7: Structured Readout / Validator Interface
Layer 8: Validator Loop
```

The entropy split is explicit:

| Entropy profile | What belongs here |
|---|---|
| low-entropy scaffold | closure, winding, validity, family priors, family geometric filters, rewrite-invariance constraints |
| high-entropy adaptation | tolerance selection under drafting style, pair-relation scoring, family-conditioned merge heads, prototype memory, reviewer feedback |

The take-home tests the scaffold. The merge lab begins to expose the next layer.

## What The File Actually Contains

The most important empirical findings:

### Normalization

`A-GLAZING MULLION` and `A-GLAZING-MULLION` are not just naming variants. They overlap strongly in space while using different primitive carriers. They are effectively the same physical mullions authored with two CAD conventions.

`A-GLAZING FULL` and `A-GLAZING-FULL` have similar names but mostly disjoint spatial zones. So naive name normalization is wrong. Spatial overlap and entity-type profile both matter.

See:

- [`../process/layer_normalization_analysis.md`](../process/layer_normalization_analysis.md)

### Programmatic vs Contextual Merges

The merge problem factors into two sequential quotients:

- **programmatic**: decidable from provenance + degenerate geometry alone
- **contextual**: requires neighborhood reasoning or learned judgment

On this file:

- all curtain-wall recommended merges are effectively programmatic
- only a small minority of wall merges are

See:

- [`programmatic_vs_contextual_merges.md`](programmatic_vs_contextual_merges.md)

### Family-Typed Structure

Columns behave like a duplicate-overlap problem.

Walls behave like a continuity-and-compatibility problem.

Curtain walls behave like a panel-lattice problem.

That is why the merge layer should be family-typed rather than monolithic.

## Why The Programmatic / Contextual Split Matters

This is not just a convenient observation about this one file.

It says that part of the merge problem has **compositional structure that survives composition**.

The programmatic quotient collapses the provenance-decidable part cheaply. The contextual quotient is the residual that actually requires learned judgment.

That is why the merge lab is worth treating as a first-class surface instead of a one-off utility.

## The Extension Plan

The extension path is already sketched in:

- [`../experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](../experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md)
- [`../experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](../experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md)

The ordering matters:

0. **Rewrite-invariance as training objective.** Generate equivalent views of the same merge relation and require stable predictions under them.
1. **Label candidate pairs** through the merge lab.
2. **Train sparse edge scorers** on pair features, ideally with calibrated uncertainty.
3. **Add prototype memory** in the small-clean-label regime.
4. **Add a GNN** only as consistency propagation across already-scored pair relations.
5. **Emit typed edit proposals / structured readouts** over typed adjacency templates and validator-facing state.

The GNN is not the first step. It is what comes after the quotient is reasonably right. The point of the scaffold is to prevent the project from collapsing into brittle edge-case patching before the scalable representation is even defined.

## What The Take-Home Proved Empirically

- A geometry-first pipeline can recover `274 / 572 / 304` walls / columns / curtain walls on the supplied file in a few seconds.
- The hyphen/space layer variants can collapse programmatically in the right cases.
- Column merge candidates separate into interpretable buckets:
  - extraction duplicates
  - distinct-but-close elements
  - ambiguous cases
- Adaptive or family-aware tolerance tuning is meaningful, but the basic scaffold already reveals stable structure.

Those are useful because they are low-entropy invariants surfaced by the scaffold, not learned artifacts.

## Reading Order

For a reviewer or interview conversation:

1. [`../../DESIGN.md`](../../DESIGN.md)
2. this document
3. [`../process/layer_normalization_analysis.md`](../process/layer_normalization_analysis.md)
4. [`programmatic_vs_contextual_merges.md`](programmatic_vs_contextual_merges.md)
5. [`../experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](../experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md)

## References

### Framing

- Lei et al., *A Mechanistic Analysis of Sim-and-Real Co-Training in Generative Robot Policies*, 2026

### Operational test / equivariance

- Brehmer, de Haan, Behrends, Cohen, *Geometric Algebra Transformers*, 2023
- de Haan, Cohen, Brehmer, *Euclidean, Projective, Conformal: Choosing a Geometric Algebra for Equivariant Transformers*, 2024
- Bronstein, Bruna, Cohen, Veličković, *Geometric Deep Learning: Grids, Groups, Graphs, Geodesics, and Gauges*, 2021

### Compositionality

- Censi, *A Mathematical Theory of Co-Design*, 2015
- Cai, Zardini et al., *Linear Design Problems and their Compositional Structure*, 2026

### Scoring / calibration / memory

- Vovk, Gammerman, Shafer, *Algorithmic Learning in a Random World*
- Goodfire, *EVEE* work on annotation probes / sparse feature bridges
- Kafraj, Krotov et al., *Dense Associative Memory with Threshold Nonlinearities*, 2026

Note: before any external-facing literature section is finalized, verify exact citation metadata and arXiv identifiers.

---

## Copy whole — reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md

Source: `reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`

# Independent Latent Dimensions Memo

Date: 2026-04-15

## Purpose

This memo sharpens the current research hypothesis:

> Primitive cleanup and merge decisions in authored architectural DXF files should factor through a small quotient of independent latent dimensions.

This is the tighter follow-on to [`../research/thesis.md`](../research/thesis.md). It also incorporates the empirical findings from [`../process/layer_normalization_analysis.md`](../process/layer_normalization_analysis.md).

The goal here is not to claim a finished theorem. The goal is to define:

- what the quotient should preserve
- what it should quotient away
- what evidence currently supports the hypothesis
- how to falsify or refine it empirically using the merge lab

## The Core Claim

The current file should not be modeled as geometry plus random noise.

It is better modeled as:

`observed_representation = R(style, decomposition, layering, snapping, carrier_choice)(latent_object_system)`

Where:

- `latent_object_system` is the intended architectural structure
- `R(...)` is a structured rewrite action induced by drafting practice

This means the right representation problem is:

- not denoising
- not unconstrained embedding compression
- but quotienting by semantics-preserving authored rewrites

That is the sense in which the user’s ACT-style analogy is useful.

## What Layer Normalization Analysis Changed

[`layer_normalization_analysis.md`](../process/layer_normalization_analysis.md) materially improved the representation picture.

Three findings matter:

### 1. Same Spatial Semantics, Different Carrier Schemas

`A-GLAZING MULLION` versus `A-GLAZING-MULLION`:

- same broad spatial region
- different primitive types
- one is `LINE` only
- the other is `LWPOLYLINE` only

Interpretation:

- this is not a typo-level naming issue
- it is a schema/convention difference over the same physical class of objects

So the quotient must identify those as equivalent for geometry extraction while preserving the provenance difference.

### 2. Similar Names, Different Zones

`A-GLAZING FULL` versus `A-GLAZING-FULL`:

- similar names
- largely disjoint spatial regions
- different entity-type richness

Interpretation:

- name normalization alone is not enough
- there is real provenance or phase information encoded in the distinction

So the quotient should not collapse them as identical provenance, even if they pool into the same family-level geometry process.

### 3. HATCH Companion Layers Are Near-Ground-Truth Carriers

Wall layers with companion HATCH layers give a second representation of the same objects:

- outline-style carriers
- fill-style carriers

Interpretation:

- this is an internal multi-view of the same latent object
- it gives us a natural equivalence class for testing representation invariance

This is extremely useful for supervision and for validating whether a proposed latent truly factors through representation choice.

## The Right Distinction: Quotient vs Residual

The most useful conceptual split is now:

- quotient coordinates
- residual provenance coordinates

Quotient coordinates:

- must stay stable across semantics-preserving drafting rewrites
- should be sufficient for cleanup and merge decisions

Residual provenance coordinates:

- retain drafting style, schema, zone, phase, or authorship information
- should not be destroyed, because they matter for debugging and future learning

This aligns with the recommendation from [`layer_normalization_analysis.md`](../process/layer_normalization_analysis.md):

> pool for geometry, tag for provenance

That is the correct move.

## Working Hypothesis

The strongest defensible claim right now is:

> Merge-relevant architectural cleanup factors through a small typed quotient over pair relations between polygon candidates, with provenance retained as a residual side channel.

Two consequences follow from this:

1. The latent object for learning is probably the candidate pair relation, not the isolated polygon.
2. The quotient is likely family-conditioned, not completely universal across walls, columns, and curtain walls.

## Candidate Independent Dimensions

I would not state an exact proven number yet.

But the current evidence supports a working relational quotient with roughly three blocks:

### Block A: Geometry Identity Invariants

These should survive semantics-preserving representation rewrites:

1. area scale
2. perimeter or boundary complexity
3. principal orientation
4. thickness
5. aspect / span ratio
6. closure / compactness

### Block B: Pairwise Merge Invariants

These determine whether two candidates should be identified or merged:

7. boundary gap
8. axial gap
9. lateral gap
10. axial overlap
11. lateral overlap
12. area ratio / scale compatibility
13. concentricity or containment
14. local continuation consistency

### Block C: Residual Provenance Coordinates

These should remain observable but should not dominate semantic equivalence:

15. layer schema identity
16. carrier choice identity
17. decomposition granularity
18. zone / phase / authorship signature

The main question is whether Block C belongs in the merge quotient itself or should remain in a side channel. My current view is:

- geometry and merge decisions should factor primarily through Blocks A and B
- Block C should remain attached as residual provenance and enter merge only as a weak prior

## Why The Candidate Pair Is The Right Learning Object

The current merge lab already points in this direction.

A polygon alone cannot express:

- continuation
- adjacency ambiguity
- duplicate-vs-distinct decisions
- same object vs same assembly

Those are relational.

That means the latent should be built over:

`x_ij = phi(polygon_i, polygon_j, local_context)`

not merely:

`x_i = phi(polygon_i)`

This is one of the most important conclusions so far.

## Current Empirical Support From Merge-Lab Distributions

The current merge-lab dataset is at:

- `out/merge_lab_data.json` (generated on demand)
- `out/merge_lab.html` (generated on demand)

Some current distributional patterns:

### Walls

- angle difference is broad
- thickness relative difference is broad
- bbox IoU is mostly near zero
- overlap features are mixed

Interpretation:

- wall merging is mostly not a duplicate-overlap problem
- it is a continuity and compatibility problem

### Columns

- boundary gaps are usually small
- IoU is often substantial
- overlaps are strong

Interpretation:

- columns are much closer to duplicate/concentric grouping
- a quotient for columns should weight overlap and scale much more heavily than wall-like continuation

### Curtain Walls

- angle differences are usually tiny
- area ratios are almost always near one
- major overlap is usually high
- minor-gap structure is the main separator

Interpretation:

- curtain-wall candidates look like regular panel lattices
- the latent likely has a stronger grid or periodicity coordinate here than in walls or columns

So even before learning anything, the three families already suggest typed quotient structure rather than one monolithic latent.

## The ACT-Style Claim I Would Actually Make

I would not currently claim:

“there are exactly N dimensions, no more, no fewer”

I would claim:

> The cleanup and merge problem appears to factor through a low-dimensional, family-typed quotient of drafting rewrites, with provenance retained as residual structure.

That statement is strong enough to be meaningful and weak enough to be honest.

The path to a stronger theorem-like statement is empirical:

- define rewrite generators
- learn or hand-specify invariants
- test whether all merge decisions factor through them

## How To Test Independence Properly

This cannot be reduced to PCA or simple variance decomposition.

The right tests are intervention and invariance tests.

### Test 1: Rewrite Invariance

Generate equivalent views of the same object relation by applying controlled rewrites:

- split/merge collinear segments
- replace circle with polyline approximation
- swap between open-line and closed-carrier forms
- perturb snap lattice within tolerance class
- remap between companion layer schemas

If the learned state changes significantly under these rewrites, it is not a valid quotient coordinate.

### Test 2: Residual Predictability

For a candidate latent dimension to be independent in the useful sense, it should not be trivially reconstructed from the others.

For each proposed dimension:

- regress it from the remaining dimensions
- measure residual predictive error

If it is almost perfectly reconstructible, it is not an independent axis.

### Test 3: Merge Decision Sufficiency

Use expert labels from the merge lab and ask:

- does a sparse linear or tree model over the proposed dimensions already achieve strong performance?

If yes, that supports the quotient.

If not, then:

- some relevant invariant is missing
- or the candidate dimensions are not the right quotient coordinates

### Test 4: Cross-File Stability

The second DXF used in follow-up should be treated as the real generalization test.

If the same low-dimensional relation space continues to work across:

- different geometry
- different drafter
- different representation habits

then we are closer to a real structural claim.

### Test 5: Family Factorization

Compare:

- one shared edge model across all families
- one shared trunk with family-conditioned heads
- fully separate family models

If separate family heads dominate, then the quotient is typed rather than universal.

## The Role Of Provenance In The Quotient Story

This is where [`layer_normalization_analysis.md`](../process/layer_normalization_analysis.md) is especially important.

It prevents a bad simplification.

There are two wrong moves:

1. do not preserve provenance at all
2. let provenance dominate semantic equivalence

The right move is:

- semantic quotient for geometry and merging
- provenance residual for debugging, auditability, and future learned priors

This is not a minor implementation detail.

It changes the form of the representation claim:

- the quotient is over semantic structure
- the residual is over drafting history and schema choice

That is a cleaner and stronger position.

## Where Hopfield Memory Fits

The user suggested Hopfield-style reconstruction logic.

I think the correct place for it is:

- not on raw primitives
- not on raw polygons
- but on pairwise merge relation states

The best use is prototype memory:

- positive bank: known good duplicate/merge relations
- negative bank: known near-but-distinct relations

Then the memory score becomes:

- not “how well does this reconstruct in general?”
- but “does this retrieve from the right equivalence class?”

This fits the current merge-lab design and the small clean data regime.

## Should We Train A Graph Embedding Next

Yes, but only after the quotient hypothesis is operationalized.

The recommended order is:

1. extract expert labels from the merge lab
2. define rewrite augmentations
3. train a sparse edge model over candidate-pair dimensions
4. add a Hopfield memory head
5. only then add a small graph model for consistency propagation

The graph model should not be the first place we look for the quotient.

It should be the place we look for residual relational structure after the quotient is already mostly right.

## The Most Important Research Question Now

The central question is:

> Is there a small typed relational quotient that makes authored drafting variants collapse cleanly while preserving the object boundaries that matter for cleanup and merging?

That is the right question.

It is sharper than:

- “what embedding should we use?”
- “should we use a GNN?”
- “is the data noisy?”

It gets the representation boundary right.

## Immediate Next Steps

The next work should be organized around falsification.

1. Add export/import of expert labels from the merge lab.
2. Construct rewrite augmentations from the current DXF carriers.
3. Build a training set of labeled candidate relations.
4. Test sparse edge models on the current pair dimensions.
5. Measure whether the same low-dimensional relation space survives rewrite augmentation and a second file.

If it survives, then the latent-dimensions hypothesis is becoming real.

If it fails, then we learn exactly which invariants are missing.

That is the current best research direction.

---

## Copy sections — README excerpts

Source: `README.md` (“How To Read This Repo” and “What the analysis found”)

### How To Read This Repo

Three layers, in this order:

#### 1. Direct Solver

Start here for the take-home answer.

- [`tokenize_dxf.py`](tokenize_dxf.py) — stdlib parser + extractor (single file)
- [`DESIGN.md`](DESIGN.md) — one-page approach + per-family strategy + failure modes
- [`out/tokenization_output.json`](out/tokenization_output.json) — graded output
- [`out/extracted_overlay.svg`](out/extracted_overlay.svg) — visual verification

#### 2. Supplementary Analysis

Read this if you want to understand the artifact beyond the count.

- [`reference/process/layer_normalization_analysis.md`](reference/process/layer_normalization_analysis.md) — why `FAMILY_LAYER_MAP` pools the hyphen/space variants
- [`reference/research/programmatic_vs_contextual_merges.md`](reference/research/programmatic_vs_contextual_merges.md) — the two-quotient decomposition with per-family evidence
- `agent_merge_review.py` + `agent_labels.json` — programmatic labelling of 87 merge candidates (run it; it produces the labels)
- `python -m augrade.cli.pipeline` — regenerates dashboard + merge lab on demand (not tracked)

This layer is about provenance, drafting variation, merge ambiguity,
and reviewability. It supports audit and annotation; it is not the
graded output.

#### 3. Future ML Framing

Read this if you want the bridge from the take-home to a learned system.

- [`reference/research/thesis.md`](reference/research/thesis.md) — structured representation alignment, the seven-layer stack, the extension plan
- [`reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](reference/experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md) — the quotient claim sharpened
- [`reference/experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](reference/experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md) — phases 0–8

The geometric solver in layer 1 is a preliminary scaffold. Layers 4+
are deliberately not built into the take-home; they are sketched as
the path forward, not pretended into the artifact.

### What the analysis found

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

---

## Copy sections — DESIGN.md “Framing”

Source: `DESIGN.md` (bottom “Framing” section)

### Framing

The implementation is intentionally a low-entropy scaffold:

- closure rules
- winding rules
- simple validity checks
- layer-name priors

The production path adds a learned high-entropy layer on top:

- learned tolerance selection by drafting style
- ambiguous polygon disambiguation with sparse interpretable features
- graph-based propagation over object tokens
- correction-driven adaptation from reviewer feedback
- rewrite-invariance under drafting-convention symmetries as a training-time augmentation, not just a post-hoc validation check

The broader framing is **structured representation alignment** in the
sense of the co-training literature: the right representation
*aligns* cross-domain views (layer-schema variants, carrier choices,
decomposition conventions) at the semantic level while *preserving
domain discernibility* (source layer, carrier kind, variant group) as
residuals. Collapsing provenance is the canonical failure mode;
pooling for geometry while tagging for provenance is the
corresponding fix. See [`reference/research/thesis.md`](reference/research/thesis.md)
for the full framing and extension plan.

