from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = (ROOT / "scripts" / "load_tab_event_payloads.sql").read_text(encoding="utf-8")
FETCHER = (ROOT / "scripts" / "fetch_tab_event_history.py").read_text(encoding="utf-8")
MIGRATION = (ROOT / "infra" / "migrations" / "012_ingestion_idempotency.sql").read_text(
    encoding="utf-8"
)
BOTTLENECK_MIGRATION = (
    ROOT / "infra" / "migrations" / "006_production_bottleneck_indexes.sql"
).read_text(encoding="utf-8")


def test_fetch_timestamp_is_auditable_and_replay_stable() -> None:
    assert 'payload["_betman_fetched_at"]' in FETCHER
    assert "EXCLUDED.fetched_at" in LOADER
    assert "tep.fetched_at AS captured_at" in LOADER


def test_loader_only_materialises_current_import() -> None:
    assert "CREATE TEMP TABLE tab_event_payloads_current" in LOADER
    assert "JOIN tab_event_import_ids imported" in LOADER
    assert "JOIN tab_event_import_ids imported ON imported.external_race_id = r.external_race_id" in LOADER


def test_available_tab_intelligence_is_materialised() -> None:
    for relation in (
        "pedigrees",
        "track_condition_readings",
        "race_data_quality",
        "odds_movements",
        "odds_analytics",
    ):
        assert f"INSERT INTO {relation}" in LOADER
    assert "flucs_with_timestamp,last_six" in LOADER


def test_non_positive_market_prices_are_rejected() -> None:
    assert "NULLIF(entry_src.runner #>> '{odds,fixed_win}', '')::numeric > 0" in LOADER
    assert "WHEN NULLIF(entry_src.runner #>> '{odds,fixed_place}', '')::numeric > 0" in LOADER
    assert "previous_price > 0" in LOADER
    assert "AND price > 0" in LOADER


def test_loader_serializes_horse_score_writes() -> None:
    assert "pg_advisory_xact_lock(hashtext('betman_horse_scores_writer'))" in LOADER


def test_market_tables_have_replay_guards() -> None:
    for index_name in (
        "ux_odds_snapshots_capture",
        "ux_fixed_odds_ticks_capture",
        "ux_tote_pools_capture",
        "ux_market_signals_capture",
        "ux_odds_movements_capture",
    ):
        assert index_name in MIGRATION


def test_clean_install_bootstraps_tab_payload_cache_before_indexes() -> None:
    create_at = BOTTLENECK_MIGRATION.index("CREATE TABLE IF NOT EXISTS tab_event_payloads")
    index_at = BOTTLENECK_MIGRATION.index("idx_tab_event_payloads_race_date_country")
    assert create_at < index_at
