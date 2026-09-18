from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MONITOR = (ROOT / "scripts" / "check_ingestion_health.sh").read_text(encoding="utf-8")


def test_monitor_covers_freshness_countries_features_and_storage() -> None:
    for evidence in (
        "payload_freshness_seconds",
        "'NZ'",
        "'AUS'",
        "'HK'",
        "analysis_features",
        "pedigrees",
        "track_conditions",
        "odds_analytics",
        "disk_used_pct",
    ):
        assert evidence in MONITOR


def test_monitor_is_persistent_and_fails_closed() -> None:
    assert "INSERT INTO ingestion_health_snapshots" in MONITOR
    assert 'if [[ "${healthy}" != "t"' in MONITOR


def test_quiet_calendar_is_not_reported_as_missing_coverage() -> None:
    assert "CASE WHEN entries = 0 THEN 1 ELSE features::numeric / entries END" in MONITOR
    assert "CASE WHEN entries = 0 THEN 1 ELSE pedigrees::numeric / entries END" in MONITOR
