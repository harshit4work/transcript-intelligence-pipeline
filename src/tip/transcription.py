"""
Whisper transcription wrapper.

- LIVE mode + an audio file (.mp3/.wav/.m4a) present -> calls the real
  OpenAI Whisper API.
- Otherwise -> reads the pre-transcribed .txt stub (this is exactly what
  Whisper's own timestamped output looks like, so downstream code never
  needs to know which path produced it).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import get_settings


@dataclass
class TranscriptionResult:
    text: str
    source: str  # "whisper_api" | "pretranscribed_stub"
    audio_path: str | None


class WhisperTranscriber:
    def __init__(self):
        self.settings = get_settings()

    def transcribe(self, path: str | Path) -> TranscriptionResult:
        path = Path(path)

        if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".mp4", ".webm"}:
            if self.settings.mode == "live" and self.settings.openai_api_key:
                return self._transcribe_live(path)
            raise RuntimeError(
                f"'{path.name}' is an audio file but no OPENAI_API_KEY is set "
                "(running in MOCK mode). Add a key to .env to transcribe real "
                "audio, or point the pipeline at a .txt transcript instead."
            )

        if path.suffix.lower() == ".txt":
            text = path.read_text(encoding="utf-8")
            return TranscriptionResult(
                text=text, source="pretranscribed_stub", audio_path=None
            )

        raise ValueError(f"Unsupported input type: {path.suffix}")

    def _transcribe_live(self, path: Path) -> TranscriptionResult:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        with open(path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        lines = []
        for seg in getattr(transcript, "segments", []) or []:
            start = _format_ts(seg["start"] if isinstance(seg, dict) else seg.start)
            text = seg["text"] if isinstance(seg, dict) else seg.text
            lines.append(f"[{start}] {text.strip()}")
        text = "\n".join(lines) if lines else transcript.text
        return TranscriptionResult(text=text, source="whisper_api", audio_path=str(path))


def _format_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
