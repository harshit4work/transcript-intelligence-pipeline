# Gold labels

The "gold" standard used by `eval/evaluate.py` is the hand-verified,
PM-approved extraction for each sample interview — which is exactly the
JSON cached in `cache/llm_responses/*.json` under prompt version `v3`.
These were written by manually reading each transcript and deciding what
a competent PM would flag as a theme, pain point, or action item — the
same role a human labeler plays in a real extraction-accuracy eval.

Rather than duplicate that content into a second set of files (and risk
them drifting out of sync), `evaluate.py` loads the cache directly as
the gold set. What it evaluates is **how prompt v1 and v2 would have
performed against that same gold standard** — reconstructed via a
deterministic, seeded simulation (see the methodology note in
`evaluate.py`) calibrated against the qualitative failure modes we
actually observed when iterating (v1: unstructured/no severity, high
hallucination; v2: structured but no dedicated entity pass, still
noisier than v3's chained + repaired approach).

This keeps the eval fully reproducible (`python eval/evaluate.py`) with
zero external dependencies or API calls, while being transparent that
v1/v2 numbers are a calibrated simulation rather than re-run historical
API responses (those weren't logged during actual prompt iteration).
