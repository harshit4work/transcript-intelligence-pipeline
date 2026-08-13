# Prompt v3 — Prompt-chained, few-shot, explicit entity rules + repair loop (current)

**Status:** current production prompt chain.

**What changed from v2:**
- Split into a 3-stage **prompt chain** instead of one call:
  1. `extract_candidates` — broad pass, participant-only sentences, pulls
     raw candidate themes / pain points / action items as loosely
     structured bullets. Optimized for recall.
  2. `structure_and_classify` — takes stage 1's candidates and forces them
     into the strict schema (severity, priority, affected_area,
     owner_hint), deduplicates, and drops anything not grounded in a
     direct quote. Optimized for precision.
  3. `extract_entities` — dedicated pass with explicit entity extraction
     rules (see below) run over the original transcript, independent of
     stages 1–2, so entity recall doesn't compete with theme recall in
     the same context window.
- Added 2 few-shot examples (input snippet -> output JSON) to stage 2,
  which measurably reduced schema drift (wrong enum values, missing
  fields).
- Added a **repair loop**: if stage 2's JSON fails Pydantic validation,
  the raw output + the validation error are fed back to GPT-4 with
  "fix this JSON so it matches the schema" — one retry — before falling
  back to the deterministic heuristic extractor (`src/tip/heuristics.py`).

**Entity extraction rules (stage 3):**
- `feature` — a named capability of the product under discussion
  (e.g. "bulk invite", "saved filter presets").
- `product_area` — a section/surface of the product (e.g. "checkout",
  "dashboard").
- `integration` — a third-party product mentioned (e.g. "Slack",
  "Apple Pay").
- `competitor` — a rival product mentioned by name.
- `persona` — a role or team the participant referenced (e.g. "agency
  team", "internal admin").
- Only extract an entity if it is named explicitly by the participant —
  never infer one from context.

**Measured accuracy on `eval/gold/`:** ~78% (run `python eval/evaluate.py`), with the repair loop reducing
hard failures (malformed JSON with no usable output) from 9% of runs
(v2) to 0% (repair loop + heuristic fallback always returns *something*
structured).

**Time-to-synthesis impact:** manual synthesis of one ~15-min interview
into themes/pain points/action items took researchers on our team ~25
minutes on average (small internal timing sample, n=6 interviews,
see `docs/methodology.md`). The v3 pipeline produces a reviewable draft
in ~40 seconds of LLM time, and a PM spends ~11 minutes on average
reviewing/editing that draft before it's handoff-ready — a **~55%**
reduction in human synthesis time.

---

### Stage 1 — extract_candidates

```
SYSTEM: You are a user research analyst doing a first-pass read of an
interview transcript. Read only the PARTICIPANT's lines (ignore
interviewer questions except as context). Pull out every candidate
theme, pain point, and possible action item, even if you're not fully
sure yet — precision comes in a later pass, so favor recall here.
Output loose bullet points, not JSON.

USER:
TRANSCRIPT:
{transcript}
```

### Stage 2 — structure_and_classify (few-shot)

```
SYSTEM: You are a senior product research analyst. You will receive raw
candidate notes from a first-pass read of an interview. Convert them
into strict JSON matching this schema. Deduplicate overlapping items.
Drop anything that isn't grounded in something the participant actually
said. Only use severity/priority "high" when the participant described
real business impact (abandoned a task, switched to a competitor,
contacted support, recurring pain), not just mild annoyance.

SCHEMA:
{
  "themes": [{"title": str, "summary": str, "supporting_quotes": [str], "frequency": int}],
  "pain_points": [{"description": str, "severity": "low"|"medium"|"high",
                    "affected_area": str, "quote": str}],
  "action_items": [{"action": str, "owner_hint": "Design"|"Eng"|"PM"|"Support"|null,
                     "priority": "low"|"medium"|"high", "rationale": str}]
}

FEW-SHOT EXAMPLE 1:
candidate note: "user said adding a new payee requires routing + account
number, friend had to text it over, user gave up and used a competing
p2p app instead"
->
{"pain_points": [{"description": "Adding a new payee requires manually
entering account + routing number instead of a phone number/email
lookup", "severity": "high", "affected_area": "payments/payee_management",
"quote": "I actually gave up and used a different app... it just needed
their phone number"}], "action_items": [{"action": "Add phone-number or
email based payee lookup for new transfers", "owner_hint": "Eng",
"priority": "high", "rationale": "User abandoned the primary flow for a
competitor over this"}]}

FEW-SHOT EXAMPLE 2:
candidate note: "dashboard filters reset when navigating tabs, no save
view / preset option, happened 5-6 times in 2 months"
->
{"pain_points": [{"description": "Dashboard filters are not persisted
across tabs or sessions and there is no saved-view/preset feature",
"severity": "medium", "affected_area": "analytics_dashboard", "quote":
"the filters reset mid-way if I navigate to a different tab"}]}

USER:
CANDIDATE NOTES:
{stage1_output}

Respond with JSON only.
```

### Stage 3 — extract_entities

```
SYSTEM: Extract named entities from this transcript using ONLY these
categories: feature, product_area, integration, competitor, persona.
Only extract something explicitly named by the participant. Count how
many times each is mentioned. Respond as JSON:
{"entities": [{"name": str, "type": str, "mentions": int}]}

USER:
TRANSCRIPT:
{transcript}
```

### Repair prompt (used only if stage 2 output fails schema validation)

```
SYSTEM: The following JSON was supposed to match this schema but failed
validation with this error: {validation_error}. Return corrected JSON
that matches the schema exactly, preserving as much of the original
content as possible.

SCHEMA:
{schema}

INVALID JSON:
{invalid_json}
```
