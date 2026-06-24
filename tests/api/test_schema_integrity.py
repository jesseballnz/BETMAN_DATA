"""
Static schema-integrity tests.

These tests parse the committed SQL migration files and assert that every
table and column the middleware/routers write to is actually declared in
the migrations.  A future migration rename will break CI here rather than
silently break production.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "infra" / "migrations"


def _read_migrations(*names: str) -> str:
    return "\n".join((MIGRATIONS_DIR / name).read_text() for name in names)


def _table_columns(sql: str, table: str) -> set[str]:
    """
    Extract column names from a CREATE TABLE ... statement for *table*.
    Handles IF NOT EXISTS and quoted identifiers.
    """
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?\"?"
        + re.escape(table)
        + r"\"?\s*\((.+?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql)
    if not match:
        return set()
    body = match.group(1)
    columns: set[str] = set()
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        if not line or line.upper().startswith(("PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "CONSTRAINT", "--")):
            continue
        col = re.match(r'"?(\w+)"?', line)
        if col:
            columns.add(col.group(1).lower())
    return columns


class TestTenantUsageSchema:
    """tenant_usage must have all columns the middleware INSERTs into."""

    EXPECTED = {"tenant_id", "endpoint", "method", "status_code", "duration_ms", "captured_at"}

    def test_table_exists_in_001(self):
        sql = (MIGRATIONS_DIR / "001_initial_schema.sql").read_text()
        assert "CREATE TABLE" in sql.upper() and "tenant_usage" in sql

    def test_required_columns_present(self):
        sql = (MIGRATIONS_DIR / "001_initial_schema.sql").read_text()
        cols = _table_columns(sql, "tenant_usage")
        missing = self.EXPECTED - cols
        assert not missing, f"tenant_usage missing columns: {missing}"


class TestAuditLogSchema:
    """audit_log must have all columns the middleware INSERTs into."""

    EXPECTED = {"tenant_id", "actor", "action", "resource", "payload_json", "ip_address", "created_at"}

    def test_table_exists_in_001(self):
        sql = (MIGRATIONS_DIR / "001_initial_schema.sql").read_text()
        assert "audit_log" in sql

    def test_required_columns_present(self):
        sql = (MIGRATIONS_DIR / "001_initial_schema.sql").read_text()
        cols = _table_columns(sql, "audit_log")
        missing = self.EXPECTED - cols
        assert not missing, f"audit_log missing columns: {missing}"


class TestTenantApiKeysSchema:
    """tenant_api_keys must include the Pass-1 columns added in migration 004."""

    BASE_EXPECTED = {"tenant_id", "key_hash", "key_prefix", "is_admin", "active"}
    MIGRATION_004_EXPECTED = {"scopes", "requests_per_minute", "daily_quota"}

    def test_base_columns_in_001(self):
        sql = (MIGRATIONS_DIR / "001_initial_schema.sql").read_text()
        cols = _table_columns(sql, "tenant_api_keys")
        missing = self.BASE_EXPECTED - cols
        assert not missing, f"tenant_api_keys missing base columns: {missing}"

    def test_004_columns_present_via_alter(self):
        sql = (MIGRATIONS_DIR / "004_api_keys_and_security.sql").read_text()
        for col in self.MIGRATION_004_EXPECTED:
            assert col in sql.lower(), f"Migration 004 does not mention column '{col}'"
