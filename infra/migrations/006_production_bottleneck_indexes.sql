\set ON_ERROR_STOP on

-- Production bottleneck indexes for hot BETMAN Data read paths.
-- Use CONCURRENTLY because these tables are live ingestion targets.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_track_conditions_race_recorded
    ON track_condition_readings (race_id, recorded_at DESC)
    WHERE race_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_track_conditions_meeting_recorded
    ON track_condition_readings (meeting_id, recorded_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_odds_race
    ON odds_snapshots (race_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_odds_entry
    ON odds_snapshots (race_entry_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_odds_captured_at
    ON odds_snapshots (race_id, captured_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_odds_entry_captured_desc
    ON odds_snapshots (race_entry_id, captured_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_odds_ticks_race
    ON fixed_odds_ticks (race_id, captured_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_odds_ticks_entry
    ON fixed_odds_ticks (race_entry_id, captured_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fixed_ticks_time
    ON fixed_odds_ticks (race_id, time_to_jump_s DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fixed_ticks_race_source_captured
    ON fixed_odds_ticks (race_id, source, captured_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tote_pools_race
    ON tote_pools (race_id, pool_type);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tote_pools_race_pool_captured
    ON tote_pools (race_id, pool_type, captured_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_smart_money_race
    ON smart_money_indicators (race_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_smart_money_confidence_detected
    ON smart_money_indicators (confidence DESC, detected_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_smart_money_entry_detected
    ON smart_money_indicators (race_entry_id, detected_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tab_event_payloads_race_date_country
    ON tab_event_payloads (race_date, country);

ANALYZE track_condition_readings;
ANALYZE odds_snapshots;
ANALYZE fixed_odds_ticks;
ANALYZE tote_pools;
ANALYZE smart_money_indicators;
ANALYZE tab_event_payloads;

INSERT INTO schema_migrations (version) VALUES ('006_production_bottleneck_indexes.sql')
ON CONFLICT (version) DO NOTHING;
