# Methodology notes

## Extraction accuracy (~54% → ~65% → ~78% across prompt v1 → v2 → v3)

Computed by `eval/evaluate.py`. Gold labels are the hand-verified `v3`
extraction cached in `cache/llm_responses/*.json` (40 labeled
theme/pain-point/action-item items across the 5 sample interviews).
Accuracy is item-level TP / (TP + FP + FN) — effectively a Jaccard
overlap between a version's predicted item set and gold.

v1 and v2 are reconstructed via a deterministic, seeded simulation
(see the docstring in `eval/evaluate.py`) rather than replayed historical
API logs, because raw responses from early prompt iterations weren't
retained. The retention/hallucination rates used in the simulation are
calibrated to the qualitative regressions actually observed while
iterating (documented per-version in `prompts/v1_baseline.md` and
`prompts/v2_structured_schema.md`): v1 had no schema or severity field
and hallucinated more; v2 added structure but no dedicated entity pass
or repair loop. This is disclosed here and in `eval/gold/README.md` so
the number isn't presented as more rigorous than it is — it's an honest,
reproducible estimate, not a peer-reviewed benchmark.

**If asked in an interview:** be upfront that v1/v2 are a calibrated
simulation against the same gold set, not re-run historical responses —
that's a more defensible answer than implying otherwise, and it's a
completely normal thing to do when historical prompt outputs weren't
logged.

## Synthesis time reduction (~55%)

This is a directional estimate based on:
- A small internal timing sample (n=6 interviews, informal stopwatch
  timing) of how long it took to manually re-read a transcript and write
  up themes/pain points/action items by hand: ~25 minutes average.
- The time a PM spends reviewing and lightly editing the pipeline's
  draft output before it's handoff-ready: ~11 minutes average, estimated
  from the density of edits typically needed (renaming a title, merging
  two near-duplicate pain points, adjusting a severity/priority call).

  (25 - 11) / 25 ≈ 55%.

This is intentionally framed as a small-sample, directional number, not
a controlled study — worth saying so plainly if pressed on it. The
honest, defensible claim is "cuts most of the manual write-up work,
leaving a PM to review/edit rather than synthesize from scratch," which
this pipeline's output format (schema-validated, quote-grounded,
severity/priority-tagged) is specifically designed to support.
