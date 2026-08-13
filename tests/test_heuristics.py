from tip.heuristics import extract_heuristic
from tip.schema import ExtractionMethod

SAMPLE = """\
[00:00:02] Interviewer: How was the signup flow?
[00:00:06] Participant: Honestly it was really confusing, I couldn't figure out where to click next.
[00:00:15] Participant: I wish there was a clearer progress indicator.
[00:00:20] Interviewer: Anything else?
[00:00:22] Participant: The Slack integration worked great though.
"""


def test_heuristic_extracts_participant_pain_language_only():
    result = extract_heuristic(SAMPLE, interview_id="t1", source_file="t1.txt")
    assert result.extraction_method == ExtractionMethod.heuristic_fallback
    assert result.confidence < 1.0
    joined = " ".join(p.description for p in result.pain_points).lower()
    assert "confusing" in joined
    # Interviewer lines must never leak into extracted pain points.
    assert "how was the signup flow" not in joined


def test_heuristic_never_raises_on_empty_transcript():
    result = extract_heuristic("", interview_id="empty", source_file="empty.txt")
    assert result.is_empty() or result.pain_points == []
    assert result.interview_id == "empty"
