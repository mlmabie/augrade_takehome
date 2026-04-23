# reference/

Docs that ship alongside the runnable pipeline. None are imported; they
exist so the tradeoffs in `augrade/` are auditable.

- [`research/thesis.md`](research/thesis.md) — short, evidence-first
  thesis grounded in this file.
- [`research/research_extension.md`](research/research_extension.md) —
  broader GenAI research framing and staged extension plan.
- [`process/layer_normalization_analysis.md`](process/layer_normalization_analysis.md) —
  empirical analysis of layer-schema variants on the supplied file and
  why `FAMILY_LAYER_MAP` pools certain hyphen/space pairs. Load-bearing
  for the extraction defaults.
- [`process/hatch_boundary_inspection.md`](process/hatch_boundary_inspection.md) —
  raw HATCH boundary-path inspection that justified stdlib parsing for
  polyline, line-edge, circular-arc, and elliptic-arc loops.
- [`research/programmatic_vs_contextual_merges.md`](research/programmatic_vs_contextual_merges.md) —
  the merge-decision split, with per-family evidence counts.
- [`experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md) —
  the representation-alignment claim in its sharpest form: merge-
  relevant cleanup factors through a small typed quotient over pair
  relations, with provenance as a residual side channel.
- [`experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md) —
  operationalization of the above: phases 0–8 from labelling through
  rewrite-invariance and small graph models.

Narrative process notes are split by audience so the root project stays
focused on the runnable solver while the research extension remains
available for readers evaluating the longer agenda.
