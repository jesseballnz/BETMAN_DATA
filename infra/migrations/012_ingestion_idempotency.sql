\set ON_ERROR_STOP on

-- Natural keys make an imported JSONL file safely replayable and stop market
-- observations from multiplying when a poll is retried.
CREATE UNIQUE INDEX IF NOT EXISTS ux_odds_snapshots_capture
    ON odds_snapshots (race_entry_id, source, captured_at)
    WHERE race_entry_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_fixed_odds_ticks_capture
    ON fixed_odds_ticks (race_entry_id, source, captured_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_tote_pools_capture
    ON tote_pools (race_id, pool_type, captured_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_market_signals_capture
    ON market_signals (race_id, COALESCE(race_entry_id, 0), signal_type, detected_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_odds_movements_capture
    ON odds_movements (race_entry_id, source, detected_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_track_condition_readings_tab_official
    ON track_condition_readings (meeting_id, COALESCE(race_id, 0), condition_code, source)
    WHERE source = 'tab_affiliate';

CREATE INDEX IF NOT EXISTS idx_prediction_snapshots_entry_generated
    ON race_prediction_snapshots (race_entry_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS ingestion_health_snapshots (
    checked_at timestamptz PRIMARY KEY,
    healthy boolean NOT NULL,
    payload_freshness_seconds integer,
    countries jsonb NOT NULL DEFAULT '{}'::jsonb,
    coverage jsonb NOT NULL DEFAULT '{}'::jsonb,
    storage jsonb NOT NULL DEFAULT '{}'::jsonb,
    failures jsonb NOT NULL DEFAULT '[]'::jsonb
);

INSERT INTO schema_migrations (version) VALUES ('012_ingestion_idempotency.sql')
ON CONFLICT (version) DO NOTHING;
