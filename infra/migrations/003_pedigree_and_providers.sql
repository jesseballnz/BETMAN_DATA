-- Migration 003: Pedigree and Provider Integrations
-- Creates provider entity mappings and pedigree tables for multi-source integration.

CREATE TABLE IF NOT EXISTS provider_entity_mappings (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL, -- 'race', 'runner', 'jockey', 'trainer'
    internal_uuid UUID NOT NULL,
    provider_name VARCHAR(50) NOT NULL, -- 'loveracing', 'racing_victoria', 'racing_nsw', 'racing_australia'
    provider_entity_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_mappings_provider_entity
    ON provider_entity_mappings(provider_name, entity_type, provider_entity_id);

CREATE INDEX IF NOT EXISTS idx_provider_mappings_internal
    ON provider_entity_mappings(entity_type, internal_uuid);

CREATE TABLE IF NOT EXISTS pedigrees (
    id SERIAL PRIMARY KEY,
    horse_uuid UUID NOT NULL,
    sire_name VARCHAR(100),
    dam_name VARCHAR(100),
    damsire_name VARCHAR(100),
    provider_name VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'pedigrees'
          AND column_name = 'horse_uuid'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_pedigrees_horse ON pedigrees(horse_uuid);
    END IF;
END $$;
