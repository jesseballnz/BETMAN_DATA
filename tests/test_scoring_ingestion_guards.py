from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1] / "services" / "scoring" / "app" / "score_engine.py"
).read_text(encoding="utf-8")


def test_recent_finished_races_are_backfilled_when_features_are_missing() -> None:
    assert "r.status = 'finished'" in SOURCE
    assert "NOT EXISTS (" in SOURCE
    assert "race_analysis_features raf" in SOURCE
    assert "FEATURE_VERSION" in SOURCE


def test_unchanged_prediction_snapshots_are_throttled() -> None:
    assert "previous.generated_at >= $3::timestamptz - interval '5 minutes'" in SOURCE
    assert "previous.market_price IS NOT DISTINCT FROM $7" in SOURCE
    assert "ABS(previous.probability - $5) < 0.0001" in SOURCE
