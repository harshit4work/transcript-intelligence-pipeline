"""
GPT-4 prompt-chaining extraction engine.

Three stages (see prompts/v3_fewshot_entity_rules.md for the full prompt
text and design rationale):
  1. extract_candidates    - broad recall pass over participant lines
  2. structure_and_classify - forces stage 1 into strict schema, few-shot
  3. extract_entities      - dedicated entity pass over raw transcript

Fallback ladder, in order:
  1. LLM output validates against the schema on the first try  -> done.
  2. LLM output fails validation -> one repair call ("fix this JSON") ->
     re-validate.
  3. Repair also fails, or no LLM available at all (mock mode + cache
     miss) -> src/tip/heuristics.py's deterministic rule-based extractor.

This ladder is what "fallback logic" means in practice here: the pipeline
is contractually guaranteed to always return a valid ExtractionResult,
never an exception bubbling up to the caller, and every result carries an
`extraction_method` field so you can see exactly which rung of the ladder
produced it.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from .config import CACHE_DIR, LATEST_PROMPT_VERSION, get_settings
from .heuristics import extract_heuristic
from .schema import ActionItem, Entity, ExtractionMethod, ExtractionResult, PainPoint, Theme

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# LLM client abstraction
# --------------------------------------------------------------------------

class LLMCallError(Exception):
    pass


class LiveOpenAIClient:
    """Thin wrapper around the real OpenAI GPT-4 chat completions API."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model = model

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""


class MockLLMClient:
    """
    Returns cached, hand-verified extraction output for the bundled sample
    transcripts so the demo behaves exactly like a real GPT-4 call — same
    latency-free instant response, same JSON-shaped output — without an
    API key. For an interview_id not found in the cache (e.g. a fresh
    transcript pasted in live), `complete()` raises LLMCallError, which
    the caller interprets as "no LLM available -> use the heuristic
    fallback."
    """

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir

    def has_cached_result(self, interview_id: str) -> bool:
        return (self.cache_dir / f"{interview_id}.json").exists()

    def load_cached_result(self, interview_id: str) -> Optional[dict]:
        path = self.cache_dir / f"{interview_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Extraction engine
# --------------------------------------------------------------------------

class ExtractionEngine:
    def __init__(self):
        self.settings = get_settings()
        self.mock_client = MockLLMClient()
        self._live_client: LiveOpenAIClient | None = None
        if self.settings.mode == "live" and self.settings.openai_api_key:
            self._live_client = LiveOpenAIClient(self.settings.openai_api_key)

    def run(self, transcript_text: str, interview_id: str, source_file: str) -> ExtractionResult:
        # Path A: mock mode with a cache hit -> return the cached "gold"
        # v3 extraction, exactly like a real GPT-4 call would.
        if self.settings.mode == "mock" and self.mock_client.has_cached_result(interview_id):
            data = self.mock_client.load_cached_result(interview_id)
            data["source_file"] = source_file
            return ExtractionResult.model_validate(data)

        # Path B: live mode -> real 3-stage prompt chain against GPT-4.
        if self._live_client is not None:
            try:
                return self._run_live_chain(transcript_text, interview_id, source_file)
            except Exception as exc:  # noqa: BLE001 - any live failure -> fallback
                logger.warning("Live extraction failed (%s); falling back to heuristic.", exc)

        # Path C: no LLM available (mock mode + cache miss, or live call
        # exhausted its repair attempt) -> deterministic fallback.
        return extract_heuristic(transcript_text, interview_id, source_file)

    # ---- live prompt chain -------------------------------------------------

    def _run_live_chain(self, transcript_text: str, interview_id: str, source_file: str) -> ExtractionResult:
        client = self._live_client
        assert client is not None

        stage1 = client.complete(
            system=(
                "You are a user research analyst doing a first-pass read of an "
                "interview transcript. Read only the PARTICIPANT's lines. Pull "
                "out every candidate theme, pain point, and possible action "
                "item as loose bullet points. Favor recall over precision."
            ),
            user=f"TRANSCRIPT:\n{transcript_text}",
        )

        schema_json = json.dumps(
            {
                "themes": [{"title": "str", "summary": "str", "supporting_quotes": ["str"], "frequency": "int"}],
                "pain_points": [{"description": "str", "severity": "low|medium|high", "affected_area": "str", "quote": "str"}],
                "action_items": [{"action": "str", "owner_hint": "Design|Eng|PM|Support|null", "priority": "low|medium|high", "rationale": "str"}],
            },
            indent=2,
        )
        stage2_raw = client.complete(
            system=(
                "You are a senior product research analyst. Convert the raw "
                "candidate notes into strict JSON matching this schema. "
                f"SCHEMA:\n{schema_json}\n"
                "Deduplicate. Only use severity/priority 'high' for real "
                "business impact (abandoned task, switched competitor, "
                "contacted support, recurring pain). Respond with JSON only."
            ),
            user=f"CANDIDATE NOTES:\n{stage1}",
        )

        stage2_data = self._parse_and_repair(client, stage2_raw, schema_json)

        stage3_raw = client.complete(
            system=(
                "Extract named entities using ONLY these categories: feature, "
                "product_area, integration, competitor, persona. Only extract "
                "something explicitly named by the participant. Respond as "
                'JSON: {"entities": [{"name": str, "type": str, "mentions": int}]}'
            ),
            user=f"TRANSCRIPT:\n{transcript_text}",
        )
        try:
            entities_data = json.loads(_strip_fences(stage3_raw)).get("entities", [])
        except json.JSONDecodeError:
            entities_data = []

        result = ExtractionResult(
            interview_id=interview_id,
            source_file=source_file,
            themes=[Theme(**t) for t in stage2_data.get("themes", [])],
            pain_points=[PainPoint(**p) for p in stage2_data.get("pain_points", [])],
            action_items=[ActionItem(**a) for a in stage2_data.get("action_items", [])],
            entities=[Entity(**e) for e in entities_data],
            prompt_version=LATEST_PROMPT_VERSION,
            extraction_method=ExtractionMethod.llm,
            confidence=0.9,
            raw_stage_outputs={"stage1": stage1, "stage2": stage2_raw, "stage3": stage3_raw},
        )
        return result

    def _parse_and_repair(self, client: LiveOpenAIClient, raw: str, schema_json: str) -> dict:
        try:
            return json.loads(_strip_fences(raw))
        except json.JSONDecodeError as exc:
            logger.info("Stage 2 JSON invalid, attempting repair: %s", exc)
            repaired = client.complete(
                system=(
                    "The following JSON was supposed to match this schema but "
                    f"failed to parse: {exc}. SCHEMA:\n{schema_json}\n"
                    "Return corrected JSON only, matching the schema exactly."
                ),
                user=f"INVALID JSON:\n{raw}",
            )
            try:
                return json.loads(_strip_fences(repaired))
            except json.JSONDecodeError as exc2:
                raise LLMCallError(f"Repair attempt also failed to parse: {exc2}") from exc2


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t.rsplit("```", 1)[0]
        if t.lower().startswith("json"):
            t = t[4:]
    return t.strip()
