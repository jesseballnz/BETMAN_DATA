#!/usr/bin/env sh
# scripts/migrate.sh — Single source of truth for BETMAN_DATA migrations.
#
# POSIX sh.  Requires: python and psql (postgresql-client) on PATH.
#
# Connection — use standard libpq env vars so the same script works everywhere:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
#
# Key-seeding env vars (optional — migration 004 skips seeding when absent):
#   ADMIN_API_KEY, WEBAPP_READONLY_API_KEY, PLATFORM_MASTER_KEY
#
# MIGRATION_DIR defaults to <repo_root>/infra/migrations (auto-detected from
# the script location so it works regardless of cwd).

set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
MIGRATION_DIR="${MIGRATION_DIR:-${SCRIPT_DIR}/../infra/migrations}"

# ---------------------------------------------------------------------------
# Helper: compute PBKDF2-HMAC-SHA256 hash of a key using PLATFORM_MASTER_KEY
# Usage: result=$(pbkdf2_hash "ENV_VAR_NAME")
# ---------------------------------------------------------------------------
pbkdf2_hash() {
    env_var="$1"
    python - <<PY
import hashlib, os
key  = os.getenv("${env_var}", "").encode()
salt = os.getenv("PLATFORM_MASTER_KEY", "").encode()
print(hashlib.pbkdf2_hmac("sha256", key, salt, 600_000).hex() if key else "")
PY
}

pbkdf2_prefix() {
    env_var="$1"
    python - <<PY
import os
print(os.getenv("${env_var}", "")[:8])
PY
}

# ---------------------------------------------------------------------------
# Compute PBKDF2-HMAC-SHA256 hashes for API key seeding (migration 004)
# ---------------------------------------------------------------------------
ADMIN_HASH=$(pbkdf2_hash "ADMIN_API_KEY")
ADMIN_PREFIX=$(pbkdf2_prefix "ADMIN_API_KEY")
WEBAPP_HASH=$(pbkdf2_hash "WEBAPP_READONLY_API_KEY")
WEBAPP_PREFIX=$(pbkdf2_prefix "WEBAPP_READONLY_API_KEY")

export PGOPTIONS="-c app.admin_api_key_hash=${ADMIN_HASH} -c app.admin_api_key_prefix=${ADMIN_PREFIX} -c app.webapp_readonly_api_key_hash=${WEBAPP_HASH} -c app.webapp_readonly_api_key_prefix=${WEBAPP_PREFIX}"

# ---------------------------------------------------------------------------
# Run all migrations (each is idempotent via IF NOT EXISTS + ON CONFLICT)
# ---------------------------------------------------------------------------
psql -f "${MIGRATION_DIR}/001_initial_schema.sql"
psql -f "${MIGRATION_DIR}/002_intelligence_layers.sql"
psql -f "${MIGRATION_DIR}/003_pedigree_and_providers.sql"
psql -f "${MIGRATION_DIR}/004_api_keys_and_security.sql"
psql -f "${MIGRATION_DIR}/005_pedigree_reconciliation.sql"

echo "All migrations applied successfully."
