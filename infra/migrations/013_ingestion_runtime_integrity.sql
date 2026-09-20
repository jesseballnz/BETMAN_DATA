\set ON_ERROR_STOP on

-- Persist the poller's systemd result in the same row as freshness and
-- coverage evidence. This prevents an otherwise-fresh partial import from
-- being recorded as healthy after a later materialisation stage fails.
ALTER TABLE ingestion_health_snapshots
    ADD COLUMN IF NOT EXISTS poller_result TEXT NOT NULL DEFAULT 'unknown';

INSERT INTO schema_migrations (version) VALUES ('013_ingestion_runtime_integrity.sql')
ON CONFLICT (version) DO NOTHING;
