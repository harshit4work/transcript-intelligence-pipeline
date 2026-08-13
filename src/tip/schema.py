"""
Output schema for the Transcript Intelligence Pipeline.

Every LLM extraction call — mock or live — is coerced into these Pydantic
models before it is allowed to flow downstream. This is the contract that
makes the Notion sync, the CLI renderer, and the Streamlit app all work off
one predictable shape, regardless of which prompt version or fallback path
produced the data.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ExtractionMethod(str, Enum):
    llm = "llm"
    llm_repaired = "llm_repaired"
    heuristic_fallback = "heuristic_fallback"


class Entity(BaseModel):
    """A named thing the participant referenced: a feature, competitor,
    integration, or persona/role."""

    name: str
    type: str = Field(description="feature | competitor | integration | persona | product_area")
    mentions: int = 1

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return v.strip()


class Theme(BaseModel):
    """A recurring topic across the interview (not necessarily negative)."""

    title: str
    summary: str
    supporting_quotes: List[str] = Field(default_factory=list)
    frequency: int = 1


class PainPoint(BaseModel):
    """A specific friction point the participant experienced."""

    description: str
    severity: Severity
    affected_area: str = Field(description="e.g. onboarding, checkout, notifications")
    quote: Optional[str] = None


class ActionItem(BaseModel):
    """A concrete, PM-actionable follow-up derived from the interview."""

    action: str
    owner_hint: Optional[str] = Field(
        default=None, description="Suggested team: Design | Eng | PM | Support"
    )
    priority: Priority
    rationale: Optional[str] = None


class ExtractionResult(BaseModel):
    """Full structured output for a single interview transcript."""

    interview_id: str
    source_file: str
    themes: List[Theme] = Field(default_factory=list)
    pain_points: List[PainPoint] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    entities: List[Entity] = Field(default_factory=list)
    prompt_version: str
    extraction_method: ExtractionMethod
    confidence: float = 1.0
    raw_stage_outputs: Optional[dict] = Field(
        default=None, description="Debug: intermediate prompt-chain outputs"
    )

    def is_empty(self) -> bool:
        return not (self.themes or self.pain_points or self.action_items)
