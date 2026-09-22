from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_migration_backfills_only_provider_horse_identity() -> None:
    sql = (ROOT / "infra/migrations/014_stable_tab_horse_identity.sql").read_text()
    assert "external_horse_id TEXT" in sql
    assert "runner->>'horse_id'" in sql
    assert "HAVING count(DISTINCT runner->>'horse_id') = 1" in sql
    assert "runner->>'name'" not in sql
    migrate = (ROOT / "scripts/migrate.sh").read_text()
    assert '014_stable_tab_horse_identity.sql' in migrate


def test_loader_persists_tab_horse_id() -> None:
    sql = (ROOT / "scripts/load_tab_event_payloads.sql").read_text()
    assert "INSERT INTO runners (external_runner_id, external_horse_id" in sql
    assert "NULLIF(runner->>'horse_id', '')" in sql
    assert "external_horse_id = COALESCE(EXCLUDED.external_horse_id" in sql


def test_runner_fit_joins_history_by_stable_horse_id() -> None:
    source = (ROOT / "services/api/app/routers/races.py").read_text()
    assert source.count("hru.external_horse_id = ru.external_horse_id") == 3
    assert source.count("ru.external_horse_id IS NOT NULL") == 3
    assert "ru.external_horse_id IS NULL AND hre.runner_id = current_entry.runner_id" not in source
