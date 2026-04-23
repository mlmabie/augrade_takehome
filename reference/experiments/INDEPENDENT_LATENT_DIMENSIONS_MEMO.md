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
