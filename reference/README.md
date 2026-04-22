# reference/

Docs that ship alongside the runnable pipeline. None are imported; they
exist so the tradeoffs in `augrade/` are auditable.

- [`THESIS.md`](THESIS.md) — task framing, structured-representation-alignment
  positioning, the seven-layer stack, and the extension plan. Start here.
- [`process/layer_normalization_analysis.md`](process/layer_normalization_analysis.md) —
  empirical analysis of layer-schema variants on the supplied file and why
  `FAMILY_LAYER_MAP` pools certain hyphen/space pairs. Load-bearing for the
  extraction defaults.
- [`research/programmatic_vs_contextual_merges.md`](research/programmatic_vs_contextual_merges.md) —
  the two-quotient decomposition of merge decisions, with per-family
  evidence counts. The most concrete finding in the repo.
- [`experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md`](experiments/INDEPENDENT_LATENT_DIMENSIONS_MEMO.md) —
  the representation-alignment claim in its sharpest form: merge-relevant
  cleanup factors through a small typed quotient over pair relations,
  with provenance as a residual side channel.
- [`experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md`](experiments/LATENT_DIMENSIONS_EXPERIMENT_CHECKLIST.md) —
  operationalization of the above: phases 0–5 from labelling through
  rewrite-invariance tests.

Narrative process notes (session journal, REPL approach plan, layer
etymology) and the pre-task exposition (big-picture brief, research
doc, implementation outline) were consolidated into `THESIS.md` and
removed from this branch. The full history is preserved on the
`main` branch for anyone who wants the process record.
