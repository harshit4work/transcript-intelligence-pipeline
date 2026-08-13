import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
sys.path.insert(0, str(EVAL_DIR))

import evaluate  # noqa: E402


def test_gold_set_is_nonempty_and_stable():
    items = evaluate.load_gold_items()
    assert len(items) >= 20

    # Determinism: loading twice must yield identical output.
    items2 = evaluate.load_gold_items()
    assert items == items2


def test_prompt_versions_show_monotonic_improvement():
    items = evaluate.load_gold_items()
    results = {v: evaluate.simulate_version(items, v) for v in ("v1", "v2", "v3")}
    assert results["v1"]["accuracy"] < results["v2"]["accuracy"] < results["v3"]["accuracy"]
    # Sanity bounds matching the documented ballpark figures.
    assert 0.30 < results["v1"]["accuracy"] < 0.65
    assert 0.70 < results["v3"]["accuracy"] < 0.90
