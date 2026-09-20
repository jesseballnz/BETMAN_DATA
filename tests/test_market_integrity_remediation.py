from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMEDIATION = (ROOT / "scripts" / "remediate_market_integrity.sql").read_text(
    encoding="utf-8"
)
MIGRATION = (ROOT / "infra" / "migrations" / "013_ingestion_runtime_integrity.sql").read_text(
    encoding="utf-8"
)
MIGRATE = (ROOT / "scripts" / "migrate.sh").read_text(encoding="utf-8")


def test_runtime_health_migration_is_idempotent_and_wired() -> None:
    assert "ADD COLUMN IF NOT EXISTS poller_result" in MIGRATION
    assert "013_ingestion_runtime_integrity.sql" in MIGRATION
    assert "013_ingestion_runtime_integrity.sql" in MIGRATE


def test_market_repair_is_bounded_to_invalid_or_replayable_data() -> None:
    assert "AND price <= 0" in REMEDIATION
    assert "AND (win_price IS NULL OR win_price <= 0)" in REMEDIATION
    assert "detected_at > created_at + interval '5 minutes'" in REMEDIATION
    assert "WHERE source = 'tab_affiliate'" in REMEDIATION
    assert "INSERT INTO odds_movements" in REMEDIATION
    assert "INSERT INTO odds_analytics" in REMEDIATION


def test_market_repair_coordinates_with_score_writers() -> None:
    assert "pg_advisory_xact_lock(hashtext('betman_market_integrity_remediation'))" in REMEDIATION
    assert "pg_advisory_xact_lock(hashtext('betman_horse_scores_writer'))" in REMEDIATION
