"""
Deterministic rule-based extractor.

This is the pipeline's *last-resort fallback* — it never calls an LLM. It
runs when:
  1. The transcript isn't in the mock-response cache (e.g. you paste in a
     brand new transcript live in the interview) AND no API key is set, or
  2. A live GPT-4 call fails validation twice in a row (see
     llm_extraction.py's repair loop).

It's intentionally simple (keyword + regex matching) so its lower recall
is honest and visible in the eval harness — it's meant to prove the
pipeline degrades gracefully instead of crashing, not to rival GPT-4.
"""
from __future__ import annotations

import re
from typing import List

from .schema import ActionItem, Entity, ExtractionMethod, ExtractionResult, PainPoint, Priority, Severity, Theme

PAIN_MARKERS = [
    "frustrat", "annoying", "confus", "couldn't", "could not", "hard to",
    "difficult", "slow", "broken", "buried", "clunky", "weird", "gave up",
    "abandon", "stuck", "no way to", "doesn't", "don't", "isn't", "not intuitive",
    "took me", "had to", "wish", "should", "would love", "defeats the purpose",
]

ACTION_MARKERS = [
    "would love", "wish", "should", "if we", "if you could", "magic wand",
    "highest impact", "would move the needle", "prioritize",
]

ENTITY_HINTS = {
    "template": "feature", "bulk invite": "feature", "onboarding checklist": "feature",
    "payee": "feature", "transfer limit": "feature", "biometric": "feature",
    "filter": "feature", "export": "feature", "dashboard": "product_area",
    "checkout": "product_area", "guest checkout": "feature", "apple pay": "integration",
    "notification": "feature", "slack": "integration", "email": "feature",
    "csv": "feature",
}

SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
SPEAKER_LINE_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s*(?:Interviewer|Participant):\s*", re.MULTILINE)


def _participant_sentences(text: str) -> List[str]:
    """Pull out participant-only lines (skip interviewer questions) and
    split them into sentences."""
    sentences = []
    for line in text.splitlines():
        m = re.match(r"^\[\d{2}:\d{2}:\d{2}\]\s*Participant:\s*(.*)", line.strip())
        if not m:
            continue
        chunk = m.group(1)
        for s in SENT_SPLIT_RE.split(chunk):
            s = s.strip()
            if s:
                sentences.append(s)
    return sentences


def extract_heuristic(text: str, interview_id: str, source_file: str) -> ExtractionResult:
    sentences = _participant_sentences(text)
    lower_full = text.lower()

    pain_points: List[PainPoint] = []
    for s in sentences:
        low = s.lower()
        if any(marker in low for marker in PAIN_MARKERS):
            pain_points.append(
                PainPoint(
                    description=s,
                    severity=Severity.medium,
                    affected_area="unclassified",
                    quote=s,
                )
            )
    pain_points = pain_points[:6]

    action_items: List[ActionItem] = []
    for s in sentences:
        low = s.lower()
        if any(marker in low for marker in ACTION_MARKERS):
            action_items.append(
                ActionItem(
                    action=s,
                    owner_hint=None,
                    priority=Priority.medium,
                    rationale="Flagged by keyword heuristic (no LLM available).",
                )
            )
    action_items = action_items[:4]

    entities: List[Entity] = []
    for phrase, etype in ENTITY_HINTS.items():
        count = lower_full.count(phrase)
        if count:
            entities.append(Entity(name=phrase, type=etype, mentions=count))

    themes: List[Theme] = []
    if pain_points:
        themes.append(
            Theme(
                title="Friction detected (heuristic pass)",
                summary=(
                    f"{len(pain_points)} sentence(s) matched pain-language keywords. "
                    "Run in LIVE or cached MOCK mode for real theme synthesis."
                ),
                supporting_quotes=[p.quote for p in pain_points[:3] if p.quote],
                frequency=len(pain_points),
            )
        )

    return ExtractionResult(
        interview_id=interview_id,
        source_file=source_file,
        themes=themes,
        pain_points=pain_points,
        action_items=action_items,
        entities=entities,
        prompt_version="heuristic",
        extraction_method=ExtractionMethod.heuristic_fallback,
        confidence=0.35,
    )
