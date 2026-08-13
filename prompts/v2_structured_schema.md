# Prompt v2 — Structured JSON schema + severity/priority

**Status:** superseded — kept for the eval harness / iteration history.

**What changed from v1:**
- Forced strict JSON output matching an explicit schema (themes,
  pain_points, action_items).
- Added `severity` (low/medium/high) to pain points and `priority` to
  action items so output is directly PM-triageable.
- Added a system instruction to only use information present in the
  transcript (reduced hallucinated pain points).

**Remaining issues (from `eval/evaluate.py`):**
- Still no dedicated entity extraction step — feature/competitor/integration
  names extracted inconsistently as part of theme summaries.
- No repair loop — a single malformed JSON response (missing comma, wrong
  enum casing) still failed the whole extraction with no retry.

**Measured accuracy on `eval/gold/`:** ~65% (run `python eval/evaluate.py`)

---

```
SYSTEM: You are a product research analyst. You will be given a raw
interview transcript. Extract ONLY information explicitly present in the
transcript — do not invent details. Respond with valid JSON matching
this schema exactly:

{
  "themes": [{"title": str, "summary": str, "supporting_quotes": [str]}],
  "pain_points": [{"description": str, "severity": "low"|"medium"|"high",
                    "affected_area": str, "quote": str}],
  "action_items": [{"action": str, "priority": "low"|"medium"|"high"}]
}

USER:
TRANSCRIPT:
{transcript}

Respond with JSON only, no markdown fences, no commentary.
```
