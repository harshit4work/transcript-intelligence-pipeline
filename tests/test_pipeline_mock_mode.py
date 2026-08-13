"""
End-to-end pipeline tests, forced into MOCK mode so they never require
network access or API keys — safe to run in CI.
"""
import os

os.environ["TIP_MODE"] = "mock"

from tip.config import SAMPLE_TRANSCRIPTS_DIR
from tip.pipeline import run_pipeline


def test_pipeline_runs_on_every_sample_transcript_and_uses_cache():
    files = sorted(SAMPLE_TRANSCRIPTS_DIR.glob("*.txt"))
    assert len(files) >= 5, "expected the bundled sample interviews to be present"

    for path in files:
        output = run_pipeline(path, push_notion=True)
        r = output.extraction
        assert r.extraction_method.value == "llm", (
            f"{path.name} should hit the mock cache, not the heuristic fallback"
        )
        assert not r.is_empty()
        assert r.pain_points, f"{path.name} should have at least one pain point in the demo cache"
        assert os.path.exists(output.json_path)
        assert os.path.exists(output.notion_markdown_path)


def test_pipeline_falls_back_to_heuristic_for_unknown_transcript(tmp_path):
    custom = tmp_path / "brand_new_interview.txt"
    custom.write_text(
        "[00:00:01] Participant: This was really frustrating and confusing to use.\n",
        encoding="utf-8",
    )
    output = run_pipeline(custom, push_notion=False)
    assert output.extraction.extraction_method.value == "heuristic_fallback"
    assert output.extraction.confidence < 1.0
