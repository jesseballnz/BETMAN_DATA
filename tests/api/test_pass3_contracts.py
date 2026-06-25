"""
Pass 3 contract tests — regression protection for route/model/schema drift.

Tests cover:
- Pedigree router: canonical horse_uuid identity, honest 404/empty responses
- Migration 005: pedigree_reconciliation column additions
- Explicitly-501 endpoints: events, search
- Wired-from-stub endpoints: feeds, runners
- Schema integrity for migration 005 additions
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer " + settings.admin_api_key}

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "infra" / "migrations"


def _read_migration(name: str) -> str:
    return (MIGRATIONS_DIR / name).read_text()


# =============================================================================
# Pedigree router contract tests
# =============================================================================


class TestPedigreeContracts:
    """Pedigree endpoints use real SQL; no fabricated data."""

    def test_get_by_runner_id_returns_404_when_no_db(self):
        """Without a DB connection, runner pedigree must 404 — not return fake 'Unknown'."""
        resp = client.get("/v1/pedigree/horses/1", headers=AUTH)
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert "pedigree" in detail.lower()
        assert "Unknown" not in resp.text, "Fabricated 'Unknown' runner name must not appear"

    def test_get_by_uuid_returns_404_when_no_db(self):
        """Without a DB connection, horse_uuid lookup must 404 — not fabricate data."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        resp = client.get(f"/v1/pedigree/horses/by-uuid/{test_uuid}", headers=AUTH)
        assert resp.status_code == 404

    def test_get_by_uuid_rejects_invalid_uuid(self):
        """Invalid UUID path parameter must be rejected before hitting DB."""
        resp = client.get("/v1/pedigree/horses/by-uuid/not-a-uuid", headers=AUTH)
        assert resp.status_code == 422

    def test_sire_performance_returns_empty_list_when_no_db(self):
        """Sire performance returns an honest empty list — not 500 or fake data."""
        resp = client.get("/v1/pedigree/sires/Winx/performance", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_sire_performance_with_filters(self):
        """Filtered sire performance accepts track/condition/distance params."""
        resp = client.get(
            "/v1/pedigree/sires/Winx/performance",
            params={"track_name": "Ellerslie", "condition_category": "heavy"},
            headers=AUTH,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_sire_affinities_returns_empty_list_when_no_db(self):
        """Sire affinities return an honest empty list."""
        resp = client.get("/v1/pedigree/sires/Winx/affinities", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_top_wet_track_sires_returns_empty_list_when_no_db(self):
        """Top wet-track sires returns an honest empty list."""
        resp = client.get("/v1/pedigree/sires/top-wet-track", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_top_wet_track_sires_accepts_params(self):
        """Top wet-track endpoint accepts condition_category, min_runners, limit."""
        resp = client.get(
            "/v1/pedigree/sires/top-wet-track",
            params={"condition_category": "soft", "min_runners": 5, "limit": 10},
            headers=AUTH,
        )
        assert resp.status_code == 200

    def test_sire_top_wet_track_route_does_not_conflict_with_sire_name(self):
        """
        The static path /sires/top-wet-track must resolve before the dynamic
        /sires/{sire_name}/performance route — FastAPI resolves these correctly
        because top-wet-track is a different endpoint registered first.
        """
        resp_static = client.get("/v1/pedigree/sires/top-wet-track", headers=AUTH)
        assert resp_static.status_code == 200
        assert isinstance(resp_static.json(), list)


# =============================================================================
# Migration 005 schema tests
# =============================================================================


class TestMigration005Schema:
    """Migration 005 must add horse_uuid to runners + pedigrees."""

    def test_migration_file_exists(self):
        assert (MIGRATIONS_DIR / "005_pedigree_reconciliation.sql").exists()

    def test_runners_horse_uuid_added(self):
        sql = _read_migration("005_pedigree_reconciliation.sql")
        assert "runners" in sql.lower()
        assert "horse_uuid" in sql.lower()
        assert "ADD COLUMN IF NOT EXISTS horse_uuid" in sql

    def test_pedigrees_horse_uuid_added(self):
        sql = _read_migration("005_pedigree_reconciliation.sql")
        # The ALTER TABLE for pedigrees must add horse_uuid
        assert re.search(
            r"ALTER\s+TABLE\s+pedigrees\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+horse_uuid",
            sql,
            re.IGNORECASE,
        )

    def test_pedigrees_provider_name_added(self):
        sql = _read_migration("005_pedigree_reconciliation.sql")
        assert "provider_name" in sql.lower()

    def test_pedigrees_updated_at_added(self):
        sql = _read_migration("005_pedigree_reconciliation.sql")
        assert "updated_at" in sql.lower()

    def test_unique_index_on_runners_horse_uuid(self):
        sql = _read_migration("005_pedigree_reconciliation.sql")
        assert "idx_runners_horse_uuid" in sql

    def test_index_on_pedigrees_horse_uuid(self):
        sql = _read_migration("005_pedigree_reconciliation.sql")
        assert "idx_pedigrees_horse_uuid" in sql

    def test_migration_tracked_in_schema_migrations(self):
        sql = _read_migration("005_pedigree_reconciliation.sql")
        assert "schema_migrations" in sql
        assert "005_pedigree_reconciliation.sql" in sql

    def test_migration_idempotent_keywords(self):
        sql = _read_migration("005_pedigree_reconciliation.sql").upper()
        assert "IF NOT EXISTS" in sql
        assert "ON CONFLICT" in sql

    def test_migrate_sh_includes_005(self):
        migrate_sh = (REPO_ROOT / "scripts" / "migrate.sh").read_text()
        assert "005_pedigree_reconciliation.sql" in migrate_sh


# =============================================================================
# Events and Search → explicit 501 tests
# =============================================================================


class TestExplicit501Endpoints:
    """Endpoints without a real implementation must return 501, not a fake 200."""

    def test_events_list_returns_501(self):
        resp = client.get("/v1/events", headers=AUTH)
        assert resp.status_code == 501
        body = resp.json()
        assert "detail" in body

    def test_search_ocr_returns_501(self):
        resp = client.get("/v1/search/ocr", params={"q": "Winx"}, headers=AUTH)
        assert resp.status_code == 501

    def test_search_transcripts_returns_501(self):
        resp = client.get("/v1/search/transcripts", params={"q": "Winx"}, headers=AUTH)
        assert resp.status_code == 501

    def test_search_similar_returns_501(self):
        resp = client.get("/v1/search/similar", params={"race_id": 1}, headers=AUTH)
        assert resp.status_code == 501

    def test_skins_resolve_returns_501(self):
        resp = client.get("/v1/skins/test-tenant", headers=AUTH)
        assert resp.status_code == 501


# =============================================================================
# Feeds router — now wired to DB
# =============================================================================


class TestFeedsWired:
    """Feeds endpoints query the DB; with no DB connection return empty/404."""

    def test_list_feeds_returns_200_with_empty_list_when_no_db(self):
        resp = client.get("/v1/feeds", headers=AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert "feeds" in body
        assert isinstance(body["feeds"], list)

    def test_get_feed_returns_404_when_no_db(self):
        resp = client.get("/v1/feeds/1", headers=AUTH)
        assert resp.status_code == 404


# =============================================================================
# Runners router — detail now wired
# =============================================================================


class TestRunnersWired:
    """Runner detail queries the DB; stub return must be gone."""

    def test_get_runner_returns_404_when_no_db(self):
        """Without DB, must 404 not return a bare {'runner_id': 1} stub."""
        resp = client.get("/v1/runners/1", headers=AUTH)
        assert resp.status_code == 404
        # The old stub returned 200 with just runner_id — ensure that's gone
        if resp.status_code == 200:
            # If somehow 200 — must be a proper RunnerDetail, not just {"runner_id": 1}
            body = resp.json()
            assert "name" in body, "Runner detail must include 'name' field"

    def test_runner_form_returns_501(self):
        resp = client.get("/v1/runners/1/form", headers=AUTH)
        assert resp.status_code == 501


# =============================================================================
# Pedigree response model contract
# =============================================================================


class TestPedigreeResponseModel:
    """Pedigree response model must include horse_uuid field."""

    def test_openapi_pedigree_detail_includes_horse_uuid(self):
        """OpenAPI schema for PedigreeDetail must declare horse_uuid."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        schemas = schema.get("components", {}).get("schemas", {})
        assert "PedigreeDetail" in schemas, "PedigreeDetail schema must be in OpenAPI spec"
        props = schemas["PedigreeDetail"].get("properties", {})
        assert "horse_uuid" in props, "PedigreeDetail must expose horse_uuid property"
        assert "runner_id" in props, "PedigreeDetail must still expose runner_id for compatibility"
