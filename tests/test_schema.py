import pytest
from pydantic import ValidationError

from tip.schema import ActionItem, ExtractionMethod, ExtractionResult, PainPoint, Priority, Severity


def test_pain_point_requires_valid_severity():
    with pytest.raises(ValidationError):
        PainPoint(description="x", severity="critical", affected_area="checkout")  # type: ignore[arg-type]

    p = PainPoint(description="x", severity="high", affected_area="checkout")
    assert p.severity == Severity.high


def test_action_item_owner_hint_optional():
    a = ActionItem(action="do the thing", priority=Priority.medium)
    assert a.owner_hint is None


def test_extraction_result_defaults_and_is_empty():
    r = ExtractionResult(
        interview_id="i1",
        source_file="f.txt",
        prompt_version="v3",
        extraction_method=ExtractionMethod.llm,
    )
    assert r.is_empty()
    assert r.themes == []
    assert r.confidence == 1.0


def test_extraction_result_round_trips_through_json():
    r = ExtractionResult(
        interview_id="i1",
        source_file="f.txt",
        prompt_version="v3",
        extraction_method=ExtractionMethod.llm,
        pain_points=[PainPoint(description="slow", severity=Severity.low, affected_area="perf")],
    )
    dumped = r.model_dump_json()
    restored = ExtractionResult.model_validate_json(dumped)
    assert restored == r
