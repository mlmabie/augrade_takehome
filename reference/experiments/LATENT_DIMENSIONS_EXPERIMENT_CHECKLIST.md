# Latent Dimensions Experiment Checklist

Date: 2026-04-15

## Goal

Test the hypothesis that cleanup and merge decisions in authored architectural DXF files factor through a small, family-typed quotient of independent latent dimensions, with provenance retained as a residual side channel.

Primary references:

- [`INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](./INDEPENDENT_LATENT_DIMENSIONS_MEMO.md)
- [`../THESIS.md`](../THESIS.md)
- [`../process/layer_normalization_analysis.md`](../process/layer_normalization_analysis.md)

Core tooling (regenerated on demand via `python -m augrade.cli.pipeline <dxf> <out>`; not tracked):

- `out/merge_lab.html`
- `out/merge_lab_data.json`
- `python -m augrade.cli.labels` (the supervised-dataset builder)

## Phase 0: Freeze The Current Substrate

- Confirm [`tokenize_dxf.py`](../../tokenize_dxf.py) and `python -m augrade.cli.merge_lab` still reproduce the current outputs.
- Keep `out/merge_lab_data.json` as the first benchmark snapshot.
- Do not change family definitions or candidate generation during the first round of latent-dimension experiments.

Success condition:

- all comparisons happen on the same candidate graph before feature-space changes start

## Phase 1: Collect Expert Labels

Use `out/merge_lab.html` (regenerated on demand).

Label policy:

- `positive`: should merge or should be treated as the same semantic object relation
- `negative`: should not merge

Sampling policy:

- label at least 30 positives and 30 negatives per family if possible
- include easy cases and ambiguous boundary cases
- deliberately sample around the decision boundary, not just obvious extremes
- include cases from different provenance patterns:
  - same layer
  - companion layers
  - hyphen/space variants
  - disjoint-zone variants

Export:

- use the merge-lab `Export Labels` button
- save the JSON package into a versioned location such as `experiments/labels/`

Success condition:

- a nontrivial labeled set exists for each family

## Phase 2: Build The First Supervised Table

Create the reusable dataset:

```bash
python3 -m augrade.cli.labels out/merge_lab_data.json path/to/exported_labels.json --output experiments/labeled_pairs
```

Outputs:

- `labeled_merge_pairs.json`
- `labeled_merge_pairs.csv`
- `labeled_merge_pairs_summary.json`

Checks:

- verify class counts
- verify family balance
- inspect a few rows for provenance correctness
- confirm candidate ids in the label file map cleanly back to the dataset

Success condition:

- one training table exists that can be used by simple models without opening the browser

## Phase 3: Baseline Models

Do not start with a GNN.

Train in this order:

1. hand-weighted heuristic score
2. sparse logistic regression
3. shallow tree / boosted tree
4. sparse prototype memory or Hopfield-style margin

Feature groups to test separately:

- geometry identity only
- pair relation only
- geometry + pair relation
- geometry + pair relation + provenance residuals

Metrics:

- precision / recall / F1
- PR-AUC
- ranking quality near the human decision boundary
- calibration
- per-family performance

Success condition:

- a sparse non-graph model gives a strong baseline and reveals which dimensions actually matter

## Phase 4: Independence Tests

The central question is not “does the model work?”  
It is “are these latent coordinates actually independent and quotient-relevant?”

### 4A. Residual Predictability

For each candidate dimension:

- regress it from the remaining dimensions
- measure out-of-sample residual error

Interpretation:

- if it is almost perfectly predicted from the others, it is not an independent axis
- if prediction fails materially, it may be carrying independent signal

### 4B. Feature Ablations

For each dimension or small block:

- remove it
- retrain the sparse baseline
- measure the drop in performance

Interpretation:

- if performance barely changes, the dimension may be redundant
- if performance drops sharply, the dimension is likely structurally important

### 4C. Family Factorization

Compare:

- one shared model for all families
- one shared trunk with family-conditioned heads
- fully separate family models

Interpretation:

- if separate heads win clearly, the quotient is typed rather than universal

Success condition:

- the useful dimension set is smaller and better motivated than the initial raw feature list

## Phase 5: Rewrite Invariance Tests

This is the most important falsification stage.

Construct controlled rewrite augmentations that should preserve semantics:

- split one line into many collinear segments
- merge collinear chains
- replace `CIRCLE` with faceted polyline
- replace compact polylines with equivalent line decompositions
- apply snap jitter within tolerance class
- swap between outline and companion HATCH-style carriers where possible
- perturb layer schema while preserving family and geometry

Then test:

- whether candidate features remain stable
- whether model predictions remain stable
- whether family-specific failure modes emerge

Success condition:

- the learned or hand-defined representation is invariant to semantics-preserving rewrites and sensitive to true object-boundary changes

## Phase 6: Provenance Residual Analysis

Use [`../process/layer_normalization_analysis.md`](../process/layer_normalization_analysis.md) explicitly here.

Questions:

- does provenance improve merge performance as a weak prior?
- does provenance dominate in a way that hurts generalization?
- which provenance signals are useful:
  - layer schema identity
  - carrier type
  - zone / spatial partition
  - companion-layer relationship

Rule:

- provenance should remain recoverable
- provenance should not be allowed to masquerade as semantic identity

Success condition:

- provenance is retained as residual structure and used only where it materially improves judgment without collapsing generalization

## Phase 7: Hopfield / Prototype Memory Tests

Prototype memory should be tested as a low-data relation prior, not as a raw-geometry model.

Banks:

- positive merge exemplars
- negative near-but-distinct exemplars

Compare:

- sparse model only
- sparse model + prototype memory margin

What to measure:

- data efficiency at very small label counts
- robustness on ambiguous candidates
- whether memory helps mostly in one family or across all families

Success condition:

- memory adds value in the low-label regime without replacing the structural feature space

## Phase 8: Small Graph Model

Only after the pair quotient is reasonably validated:

- build a graph over polygon candidates
- keep current pair features as edge features
- use local neighborhood context and component consistency

Target:

- not “discover geometry from scratch”
- but propagate consistency and context over the candidate relation graph

Compare against:

- best sparse non-graph baseline
- best sparse + memory baseline

Success condition:

- the graph model adds clear value on consistency-heavy cases rather than just reproducing what the edge features already know

## Deliverables To Produce During The Experiment

Minimal artifact set:

- versioned label exports
- labeled merge-pair dataset
- baseline model comparison table
- feature ablation report
- rewrite invariance report
- provenance residual report
- memory ablation report
- graph-vs-non-graph comparison report

## Red Flags

Stop and reassess if any of these happen:

- provenance features dominate all predictive power
- one family behaves completely differently and collapses a shared latent story
- rewrite augmentations break predictions badly
- the sparse baselines fail even with enough labels
- graph models help only because the pair feature space is incomplete

## The Main Falsifiable Claim

By the end of this checklist, the question should be answerable:

> Do cleanup and merge decisions factor through a small, typed, rewrite-stable latent relation space, or is the current feature set missing critical invariants?

That is the experiment.
