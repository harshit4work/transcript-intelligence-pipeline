"""
Central configuration + mode detection.

The pipeline runs in one of two modes:

- LIVE: real calls to OpenAI (Whisper + GPT-4) and the Notion API.
- MOCK: zero external calls. Uses cached, hand-verified LLM responses for
  the bundled sample transcripts (so the demo looks/feels exactly like
  live GPT-4 output) and a deterministic rule-based extractor as a
  fallback for anything not in the cache (e.g. a transcript you paste in
  yourself during the interview).

Mode is auto-detected from environment variables unless TIP_MODE forces it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT_DIR / "cache" / "llm_responses"
OUTPUT_DIR = ROOT_DIR / "output"
PROMPTS_DIR = ROOT_DIR / "prompts"
SAMPLE_TRANSCRIPTS_DIR = ROOT_DIR / "sample_data" / "transcripts"
EVAL_DIR = ROOT_DIR / "eval"

LATEST_PROMPT_VERSION = "v3"


@dataclass(frozen=True)
class Settings:
    mode: str  # "live" | "mock"
    openai_api_key: str | None
    notion_token: str | None
    notion_database_id: str | None


def get_settings() -> Settings:
    forced = os.getenv("TIP_MODE", "auto").lower()
    openai_key = os.getenv("OPENAI_API_KEY") or None
    notion_token = os.getenv("NOTION_TOKEN") or None
    notion_db = os.getenv("NOTION_DATABASE_ID") or None

    if forced == "live":
        mode = "live"
    elif forced == "mock":
        mode = "mock"
    else:
        mode = "live" if openai_key else "mock"

    return Settings(
        mode=mode,
        openai_api_key=openai_key,
        notion_token=notion_token,
        notion_database_id=notion_db,
    )
