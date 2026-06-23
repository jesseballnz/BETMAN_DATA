-- Migration 003: Pedigree and Provider Integrations
-- Creates provider entity mappings and pedigree tables for multi-source integration.

CREATE TABLE provider_entity_mappings (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL, -- 'race', 'runner', 'jockey', 'trainer'
    internal_uuid UUID NOT NULL,
    provider_name VARCHAR(50) NOT NULL, -- 'loveracing', 'racing_nsw', 'racing_australia'
    provider_entity_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider_name, entity_type, provider_entity_id)
);

CREATE INDEX idx_provider_mappings_internal ON provider_entity_mappings(entity_type, internal_uuid);

CREATE TABLE pedigrees (
    id SERIAL PRIMARY KEY,
    horse_uuid UUID NOT NULL,
    sire_name VARCHAR(100),
    dam_name VARCHAR(100),
    damsire_name VARCHAR(100),
    provider_name VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pedigrees_horse ON pedigrees(horse_uuid);
