-- =============================================================================
-- BETMAN_DATA — Pedigree Reconciliation Migration
-- 005_pedigree_reconciliation.sql
--
-- Canonicalises horse identity as horse_uuid across runners and pedigrees.
--
-- Context:
--   Migration 002 created pedigrees keyed on runner_id (INTEGER).
--   Migration 003 intended to introduce horse_uuid but its CREATE TABLE was
--   silently skipped (IF NOT EXISTS) because 002 already owned the table.
--   This migration reconciles the two intents into one canonical shape.
--
-- Apply after 004_api_keys_and_security.sql:
--   psql $DATABASE_URL -f infra/migrations/005_pedigree_reconciliation.sql
--
-- This migration is idempotent (IF NOT EXISTS / IF column_name ... guards).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Add horse_uuid to runners — the canonical identity column
-- ---------------------------------------------------------------------------
ALTER TABLE runners ADD COLUMN IF NOT EXISTS horse_uuid UUID;

CREATE UNIQUE INDEX IF NOT EXISTS idx_runners_horse_uuid
    ON runners (horse_uuid)
    WHERE horse_uuid IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. Reconcile pedigrees: add horse_uuid, provider tracking, updated_at
--    (Migration 003 intended these columns but was silently no-op'd)
-- ---------------------------------------------------------------------------
ALTER TABLE pedigrees ADD COLUMN IF NOT EXISTS horse_uuid UUID;
ALTER TABLE pedigrees ADD COLUMN IF NOT EXISTS provider_name TEXT;
ALTER TABLE pedigrees ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Index for canonical horse_uuid lookups
CREATE INDEX IF NOT EXISTS idx_pedigrees_horse_uuid
    ON pedigrees (horse_uuid)
    WHERE horse_uuid IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. Backfill pedigrees.horse_uuid from runners.horse_uuid where available
-- ---------------------------------------------------------------------------
UPDATE pedigrees p
SET horse_uuid = r.horse_uuid
FROM runners r
WHERE p.runner_id = r.id
  AND r.horse_uuid IS NOT NULL
  AND p.horse_uuid IS NULL;

-- ---------------------------------------------------------------------------
-- 4. Ensure provider_entity_mappings has an index for horse UUID lookups
--    (runner entity type is the canonical mapping for horse identity)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_provider_mappings_runner_uuid
    ON provider_entity_mappings (internal_uuid)
    WHERE entity_type = 'runner';

-- ---------------------------------------------------------------------------
-- 5. Track this migration
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version)
VALUES ('005_pedigree_reconciliation.sql')
ON CONFLICT (version) DO NOTHING;
