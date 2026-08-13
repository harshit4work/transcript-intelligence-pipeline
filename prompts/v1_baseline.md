# Prompt v1 — Baseline single-shot extraction

**Status:** superseded — kept for the eval harness / iteration history.

**Approach:** one GPT-4 call, ask for everything at once, minimal formatting
guidance, no explicit JSON schema.

**Measured issues (from `eval/evaluate.py`):**
- Free-text output required brittle regex post-processing to parse.
- No severity/priority fields — everything came back flat, unusable for
  PM triage.
- Entity extraction was inconsistent — sometimes skipped competitor/feature
  names entirely.
- No fallback path — a malformed response just failed the run.

**Measured accuracy on `eval/gold/`:** ~54% (run `python eval/evaluate.py`)

---

```
SYSTEM: You are a helpful assistant that reads user research interview
transcripts and summarizes them for a product manager.

USER: Here is an interview transcript. List the main themes, any
problems the user mentioned, and anything we should do about it.

TRANSCRIPT:
{transcript}
```
