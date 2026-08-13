"""
End-to-end orchestrator: audio/transcript -> Whisper -> GPT-4 prompt chain
-> schema-validated result -> JSON + Notion-ready output on disk.

This is the single entry point both the CLI and the Streamlit app call,
so "the platform" is really just two thin front ends over one pipeline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .config import OUTPUT_DIR, get_settings
from .llm_extraction import ExtractionEngine
from .notion_sync import push_to_notion, render_notion_markdown
from .schema import ExtractionResult
from .transcription import TranscriptionResult, WhisperTranscriber

ProgressFn = Optional[Callable[[str, str], None]]  # (stage, message) -> None


@dataclass
class PipelineOutput:
    interview_id: str
    transcription: TranscriptionResult
    extraction: ExtractionResult
    json_path: str
    notion_markdown_path: str
    notion_destination: str


def run_pipeline(
    input_path: str | Path,
    interview_id: Optional[str] = None,
    push_notion: bool = True,
    on_progress: ProgressFn = None,
) -> PipelineOutput:
    def emit(stage: str, message: str) -> None:
        if on_progress:
            on_progress(stage, message)

    input_path = Path(input_path)
    interview_id = interview_id or input_path.stem

    emit("transcribe", f"Transcribing {input_path.name} with Whisper…")
    transcriber = WhisperTranscriber()
    transcription = transcriber.transcribe(input_path)
    emit("transcribe", f"Transcription complete ({transcription.source}), {len(transcription.text)} chars.")

    emit("extract", "Running GPT-4 prompt chain (candidates → structure → entities)…")
    engine = ExtractionEngine()
    result = engine.run(transcription.text, interview_id=interview_id, source_file=str(input_path))
    emit(
        "extract",
        f"Extraction complete via `{result.extraction_method.value}` "
        f"(prompt {result.prompt_version}, confidence {result.confidence:.2f}): "
        f"{len(result.themes)} themes, {len(result.pain_points)} pain points, "
        f"{len(result.action_items)} action items, {len(result.entities)} entities.",
    )

    emit("persist", "Writing structured JSON output…")
    json_dir = OUTPUT_DIR / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / f"{interview_id}.json"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    emit("persist", "Rendering Notion-ready markdown…")
    md_dir = OUTPUT_DIR / "notion_markdown"
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{interview_id}.md"
    md_path.write_text(render_notion_markdown(result), encoding="utf-8")

    notion_destination = ""
    if push_notion:
        settings = get_settings()
        emit(
            "notion",
            f"Pushing to Notion ({'live workspace' if settings.mode == 'live' and settings.notion_token else 'local mock preview'})…",
        )
        notion_destination = push_to_notion(result)
        emit("notion", f"Notion sync complete → {notion_destination}")

    return PipelineOutput(
        interview_id=interview_id,
        transcription=transcription,
        extraction=result,
        json_path=str(json_path),
        notion_markdown_path=str(md_path),
        notion_destination=notion_destination,
    )
