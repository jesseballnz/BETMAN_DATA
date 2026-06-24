-- =============================================================================
-- BETMAN_DATA — Intelligence Layers Migration
-- 002_intelligence_layers.sql
--
-- Adds all 12 intelligence layer tables on top of the base schema.
-- Apply after 001_initial_schema.sql:
--   psql $DATABASE_URL -f infra/migrations/002_intelligence_layers.sql
-- =============================================================================

-- =============================================================================
-- LAYER 1 ENHANCEMENTS — Race Data
-- =============================================================================

-- Enrich races with additional fields
ALTER TABLE races ADD COLUMN IF NOT EXISTS stake         NUMERIC;
ALTER TABLE races ADD COLUMN IF NOT EXISTS track_direction TEXT; -- clockwise, anti-clockwise
ALTER TABLE races ADD COLUMN IF NOT EXISTS rail_position  TEXT; -- "Rail True", "+3m", "-2m"
ALTER TABLE races ADD COLUMN IF NOT EXISTS conditions_description TEXT;

-- Enrich race entries with runner profile data
ALTER TABLE race_entries ADD COLUMN IF NOT EXISTS age              INTEGER;
ALTER TABLE race_entries ADD COLUMN IF NOT EXISTS sex              TEXT;    -- M, G, F, C, R (Mare, Gelding, Filly, Colt, Rig)
ALTER TABLE race_entries ADD COLUMN IF NOT EXISTS career_starts    INTEGER;
ALTER TABLE race_entries ADD COLUMN IF NOT EXISTS career_wins      INTEGER;
ALTER TABLE race_entries ADD COLUMN IF NOT EXISTS days_since_last_run INTEGER;
ALTER TABLE race_entries ADD COLUMN IF NOT EXISTS gear_changes_json JSONB;  -- {added: ["blinkers"], removed: ["tongue_tie"]}
ALTER TABLE race_entries ADD COLUMN IF NOT EXISTS run_number_this_prep INTEGER; -- 1=first-up, 2=second-up, etc.

-- Detailed race results per entry
CREATE TABLE IF NOT EXISTS race_results (
    id              SERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL UNIQUE REFERENCES race_entries (id),
    finish_position INTEGER NOT NULL,
    margin_lengths  REAL,           -- distance from winner (0 if winner)
    in_running      TEXT,           -- position at each call, e.g. "3-2-1"
    finish_time_s   REAL,           -- total race time in seconds
    split_600m_s    REAL,           -- last 600m split
    split_400m_s    REAL,           -- last 400m split
    split_200m_s    REAL,           -- last 200m split
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_race_results_race  ON race_results (race_id);
CREATE INDEX IF NOT EXISTS idx_race_results_entry ON race_results (race_entry_id);

-- Sectional times at defined checkpoints within a race
CREATE TABLE IF NOT EXISTS race_sectionals (
    id              BIGSERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    checkpoint_m    INTEGER NOT NULL,   -- e.g. 200, 400, 600, 800 metres from finish
    time_s          REAL NOT NULL,      -- time for this sectional split
    position_at     INTEGER,            -- race position at this checkpoint
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sectionals_race  ON race_sectionals (race_id);
CREATE INDEX IF NOT EXISTS idx_sectionals_entry ON race_sectionals (race_entry_id);

-- Speed ratings per runner per race
CREATE TABLE IF NOT EXISTS speed_ratings (
    id              SERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL UNIQUE REFERENCES race_entries (id),
    rating          REAL NOT NULL,      -- standardised speed rating
    rating_method   TEXT NOT NULL,      -- timeform, beyer, betman_sr, etc.
    time_adjusted   REAL,              -- time adjusted for conditions
    class_adjusted  REAL,              -- adjusted for race class
    track_variant   REAL,              -- track speed variant applied
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- LAYER 2 ENHANCEMENTS — Market Intelligence
-- =============================================================================

-- Every single odds tick — high volume, partition by month in production
CREATE TABLE IF NOT EXISTS fixed_odds_ticks (
    id              BIGSERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    price           NUMERIC NOT NULL,
    source          TEXT NOT NULL,      -- tab_fixed, sportsbet, bet365, betfair, etc.
    captured_at     TIMESTAMPTZ NOT NULL,
    time_to_jump_s  INTEGER,            -- seconds before scheduled start
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_odds_ticks_race    ON fixed_odds_ticks (race_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_odds_ticks_entry   ON fixed_odds_ticks (race_entry_id, captured_at);

-- Tote pool sizes and dividends
CREATE TABLE IF NOT EXISTS tote_pools (
    id              SERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    pool_type       TEXT NOT NULL,      -- win, place, exacta, trifecta, first_four, quaddie
    pool_size       NUMERIC,            -- total pool in dollars
    captured_at     TIMESTAMPTZ NOT NULL,
    -- Dividend fields (populated post-race for result pools)
    combination_json JSONB,             -- e.g. {"1st": 5, "2nd": 2} for exacta
    dividend        NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tote_pools_race ON tote_pools (race_id, pool_type);

-- Calculated market signals
CREATE TABLE IF NOT EXISTS market_signals (
    id              BIGSERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER REFERENCES race_entries (id), -- NULL for race-level signals
    signal_type     TEXT NOT NULL,   -- steamer, drifter, late_money, price_compression,
                                     -- smart_money, field_compression, market_reversal
    magnitude       REAL NOT NULL,   -- signal strength 0–1
    detected_at     TIMESTAMPTZ NOT NULL,
    time_to_jump_s  INTEGER,
    evidence_json   JSONB,           -- supporting data (price movements, pool changes)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_market_signals_race ON market_signals (race_id, detected_at);
CREATE INDEX IF NOT EXISTS idx_market_signals_type ON market_signals (signal_type, detected_at);

-- Smart money indicators — higher-level synthesis
CREATE TABLE IF NOT EXISTS smart_money_indicators (
    id              SERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    indicator_type  TEXT NOT NULL,    -- coordinated_firm, tote_fixed_alignment, sharp_move, syndicate_pattern
    confidence      REAL NOT NULL,    -- 0–1
    evidence_ids    INTEGER[],        -- IDs of contributing market_signals
    detected_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_smart_money_race ON smart_money_indicators (race_id);

-- =============================================================================
-- LAYER 4 — Heatmap Intelligence
-- =============================================================================

-- One session per horse per race occasion (parade ring capture)
CREATE TABLE IF NOT EXISTS heatmap_sessions (
    id              SERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    runner_id       INTEGER NOT NULL REFERENCES runners (id),
    captured_at     TIMESTAMPTZ NOT NULL,
    operator        TEXT,             -- who/what captured the data
    camera_type     TEXT,             -- infrared, visible, combined
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_heatmap_sessions_race  ON heatmap_sessions (race_id);
CREATE INDEX IF NOT EXISTS idx_heatmap_sessions_runner ON heatmap_sessions (runner_id);

-- Infrared-derived scores per session
CREATE TABLE IF NOT EXISTS heatmap_scores (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER UNIQUE NOT NULL REFERENCES heatmap_sessions (id),
    sweating_score  REAL,             -- 0–10
    hot_zones_json  JSONB,            -- {neck: 0.8, flanks: 0.4, legs: 0.2, ...}
    symmetry_score  REAL,             -- 0–1 (1 = perfect left/right symmetry)
    recovery_score  REAL,             -- 0–1 (1 = rapid post-exercise cooling)
    coat_uniformity REAL,             -- 0–1
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- CSI (Cardiovascular + Stress Index) sensor readings
CREATE TABLE IF NOT EXISTS csi_readings (
    id                      BIGSERIAL PRIMARY KEY,
    session_id              INTEGER NOT NULL REFERENCES heatmap_sessions (id),
    captured_at             TIMESTAMPTZ NOT NULL,
    heart_rate              REAL,     -- BPM
    heart_rate_variability  REAL,     -- HRV in ms (higher = calmer)
    breathing_rate          REAL,     -- breaths per minute
    motion_score            REAL,     -- 0–10 accelerometer-based agitation
    skin_temperature_c      REAL,
    signal_quality          REAL,     -- 0–1 sensor confidence
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_csi_readings_session ON csi_readings (session_id);

-- =============================================================================
-- LAYER 5 — Pedigree Intelligence
-- =============================================================================

CREATE TABLE IF NOT EXISTS pedigrees (
    id              SERIAL PRIMARY KEY,
    runner_id       INTEGER UNIQUE NOT NULL REFERENCES runners (id),
    sire            TEXT,
    dam             TEXT,
    damsire         TEXT,             -- dam's sire
    grandsire_pat   TEXT,             -- paternal grandsire
    grandsire_mat   TEXT,             -- maternal grandsire
    family_line     TEXT,             -- Bruce Lowe family number or equivalent
    colour          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Calculated affinities per sire line × context
CREATE TABLE IF NOT EXISTS pedigree_affinities (
    id                  SERIAL PRIMARY KEY,
    sire                TEXT NOT NULL,
    affinity_type       TEXT NOT NULL,  -- wet_track, distance, track, barrier, age_progression
    context_track       TEXT,           -- NULL = all tracks
    context_distance_band TEXT,         -- NULL = all distances
    context_condition   TEXT,           -- NULL = all conditions
    affinity_score      REAL NOT NULL,  -- relative to expectation: 1.0 = neutral, >1 = positive
    win_rate            REAL,
    sample_size         INTEGER,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (sire, affinity_type, context_track, context_distance_band, context_condition)
);
CREATE INDEX IF NOT EXISTS idx_pedigree_affinities_sire ON pedigree_affinities (sire, affinity_type);

-- Aggregated sire line performance
CREATE TABLE IF NOT EXISTS bloodline_performance (
    id              SERIAL PRIMARY KEY,
    sire            TEXT NOT NULL,
    track_name      TEXT,             -- NULL = all tracks
    surface         TEXT,             -- NULL = all surfaces
    condition_category TEXT,          -- NULL = all conditions
    distance_band   TEXT,             -- NULL = all distances
    runners         INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    places          INTEGER NOT NULL DEFAULT 0,
    win_rate        REAL,
    place_rate      REAL,
    avg_win_price   REAL,
    roi             REAL,             -- return on investment at SP
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (sire, track_name, surface, condition_category, distance_band)
);
CREATE INDEX IF NOT EXISTS idx_bloodline_perf_sire ON bloodline_performance (sire);

-- =============================================================================
-- LAYER 6 — Human Intelligence
-- =============================================================================

-- Trainer aggregated performance by context
CREATE TABLE IF NOT EXISTS trainer_stats (
    id              SERIAL PRIMARY KEY,
    trainer         TEXT NOT NULL,
    track_name      TEXT,             -- NULL = all tracks
    surface         TEXT,
    condition_category TEXT,
    distance_band   TEXT,
    race_class_group TEXT,
    run_number      INTEGER,          -- 1=first-up, 2=second-up, NULL=all
    runners         INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    places          INTEGER NOT NULL DEFAULT 0,
    win_rate        REAL,
    roi             REAL,
    avg_win_price   REAL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (trainer, track_name, surface, condition_category, distance_band, race_class_group, run_number)
);
CREATE INDEX IF NOT EXISTS idx_trainer_stats_trainer ON trainer_stats (trainer);

-- Trainer-specific patterns (first-up, gear changes, class drops, etc.)
CREATE TABLE IF NOT EXISTS trainer_patterns (
    id              SERIAL PRIMARY KEY,
    trainer         TEXT NOT NULL,
    pattern_type    TEXT NOT NULL,  -- first_up, second_up, gear_change_on, class_drop,
                                    -- class_rise, distance_step_up, distance_step_down
    runners         INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    win_rate        REAL,
    roi             REAL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (trainer, pattern_type)
);

-- Jockey aggregated performance by context
CREATE TABLE IF NOT EXISTS jockey_stats (
    id              SERIAL PRIMARY KEY,
    jockey          TEXT NOT NULL,
    track_name      TEXT,
    gate_zone       TEXT,             -- inside_third, middle_third, outside_third
    going           TEXT,             -- wet (heavy/soft), dry (good/firm), all
    race_style      TEXT,             -- front_runner, tracker, midfield, backmarker
    runners         INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    win_rate        REAL,
    roi             REAL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (jockey, track_name, gate_zone, going, race_style)
);
CREATE INDEX IF NOT EXISTS idx_jockey_stats_jockey ON jockey_stats (jockey);

-- Stable signals — detected betting/drifting patterns per trainer
CREATE TABLE IF NOT EXISTS stable_signals (
    id              BIGSERIAL PRIMARY KEY,
    trainer         TEXT NOT NULL,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    signal_type     TEXT NOT NULL,    -- bet, drift, neutral
    confidence      REAL NOT NULL,
    market_move_pct REAL,             -- % movement in final 30 minutes
    detected_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_stable_signals_trainer ON stable_signals (trainer, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_stable_signals_race    ON stable_signals (race_id);

-- =============================================================================
-- LAYER 7 — Horse Behaviour Intelligence
-- =============================================================================

-- Individual behaviour observations (parade ring, loading, any stage)
CREATE TABLE IF NOT EXISTS behaviour_observations (
    id              BIGSERIAL PRIMARY KEY,
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    runner_id       INTEGER NOT NULL REFERENCES runners (id),
    stage           TEXT NOT NULL,    -- parade_ring, mounting_yard, barriers, loading
    attribute       TEXT NOT NULL,    -- sweating_level, agitation_score, head_carriage,
                                      -- coat_condition, loading_speed, loading_attempts,
                                      -- reluctance_flag, muscle_tone, walk_rhythm
    value_numeric   REAL,
    value_text      TEXT,
    captured_at     TIMESTAMPTZ NOT NULL,
    observer        TEXT,             -- human, camera_ai, sensor
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_behaviour_race   ON behaviour_observations (race_entry_id);
CREATE INDEX IF NOT EXISTS idx_behaviour_runner ON behaviour_observations (runner_id, stage);

-- Derived race style profiles per runner (built from race_sectionals + in_running data)
CREATE TABLE IF NOT EXISTS race_style_profiles (
    id              SERIAL PRIMARY KEY,
    runner_id       INTEGER NOT NULL REFERENCES runners (id),
    track_name      TEXT,             -- NULL = all tracks
    distance_band   TEXT,
    dominant_style  TEXT NOT NULL,    -- leader, on_pace, midfield, backmarker
    style_json      JSONB,            -- {leader: 0.1, on_pace: 0.3, midfield: 0.5, backmarker: 0.1}
    sample_size     INTEGER,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (runner_id, track_name, distance_band)
);

-- =============================================================================
-- LAYER 8 — Gate Intelligence / Gate Advantage Score (GAS)
-- =============================================================================

CREATE TABLE IF NOT EXISTS gate_advantage_scores (
    id                  SERIAL PRIMARY KEY,
    track_name          TEXT NOT NULL,
    surface             TEXT NOT NULL,
    distance_band       TEXT NOT NULL,
    condition_category  TEXT NOT NULL,
    condition_code      TEXT,           -- specific code, NULL = all in category
    field_size_band     TEXT NOT NULL,
    barrier_number      INTEGER NOT NULL,
    relative_barrier    TEXT NOT NULL,
    gas_raw             REAL NOT NULL,  -- (observed / expected) - 1
    gas_score           REAL NOT NULL,  -- normalised 0–100
    sample_size         INTEGER NOT NULL,
    confidence          REAL,           -- 0–1 based on sample size
    -- Modifiers applied
    rail_adjustment     REAL DEFAULT 0, -- adjustment for current rail position
    moisture_adjustment REAL DEFAULT 0, -- adjustment for soil moisture at rail
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (track_name, surface, distance_band, condition_category, condition_code, field_size_band, barrier_number)
);
CREATE INDEX IF NOT EXISTS idx_gas_lookup ON gate_advantage_scores (track_name, surface, condition_category);

-- =============================================================================
-- LAYER 9 — Track Intelligence / Track Bias Index (TBI)
-- =============================================================================

-- Per-race observations of running bias
CREATE TABLE IF NOT EXISTS track_bias_records (
    id              BIGSERIAL PRIMARY KEY,
    track_name      TEXT NOT NULL,
    race_date       DATE NOT NULL,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    bias_type       TEXT NOT NULL,    -- rail, outside, pace, headwind
    magnitude       REAL NOT NULL,    -- -1 to +1 (positive = bias toward this style)
    confidence      REAL,
    source          TEXT,             -- observed, calculated
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tbi_records_track ON track_bias_records (track_name, race_date);

-- Aggregated TBI per meeting
CREATE TABLE IF NOT EXISTS track_bias_index (
    id              SERIAL PRIMARY KEY,
    track_name      TEXT NOT NULL,
    race_date       DATE NOT NULL,
    tbi_rail        REAL,             -- rail bias: positive = inside advantage
    tbi_outside     REAL,             -- outside bias: positive = wide advantage
    tbi_pace        REAL,             -- pace bias: positive = front runners winning
    tbi_composite   REAL,             -- weighted composite
    races_in_sample INTEGER,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (track_name, race_date)
);
CREATE INDEX IF NOT EXISTS idx_tbi_track ON track_bias_index (track_name, race_date DESC);

-- Wind records for each straight (sourced from weather_stations)
CREATE TABLE IF NOT EXISTS track_wind_records (
    id                      BIGSERIAL PRIMARY KEY,
    track_name              TEXT NOT NULL,
    recorded_at             TIMESTAMPTZ NOT NULL,
    wind_speed_kmh          REAL,
    wind_direction_deg      SMALLINT,
    straight_wind_effect    TEXT,  -- headwind, tailwind, crosswind_left, crosswind_right
    straight_wind_kmh       REAL,  -- component of wind along the straight
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wind_track ON track_wind_records (track_name, recorded_at DESC);

-- =============================================================================
-- LAYER 10 — Betting Intelligence
-- =============================================================================

-- Anonymised subscriber bets (subscriber identified only by hash)
CREATE TABLE IF NOT EXISTS subscriber_bets (
    id              BIGSERIAL PRIMARY KEY,
    subscriber_hash TEXT NOT NULL,    -- SHA-256 of subscriber_id — never store plaintext
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    bet_type        TEXT NOT NULL,    -- win, place, each_way, exacta, trifecta
    stake           NUMERIC,          -- optional — may be omitted
    price_taken     NUMERIC,
    result          TEXT,             -- win, place, lose, void
    profit_loss     NUMERIC,          -- calculated post-race
    signals_active  TEXT[],           -- which BETMAN signals were active: ["GAS", "MIS", "SIS"]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sub_bets_hash  ON subscriber_bets (subscriber_hash, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sub_bets_race  ON subscriber_bets (race_id);

-- Aggregated signal performance — which signals produce ROI
CREATE TABLE IF NOT EXISTS signal_performance (
    id              SERIAL PRIMARY KEY,
    signal_type     TEXT NOT NULL,    -- GAS, MIS, SIS, TBI, WAS, BMS, BC, alpha
    period_days     INTEGER NOT NULL, -- 7, 30, 90, 365
    bets            INTEGER NOT NULL DEFAULT 0,
    winners         INTEGER NOT NULL DEFAULT 0,
    stake_total     NUMERIC,
    returns_total   NUMERIC,
    roi             REAL,             -- (returns - stake) / stake
    strike_rate     REAL,
    avg_win_price   REAL,
    edge            REAL,             -- estimated edge over market
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (signal_type, period_days)
);

-- =============================================================================
-- LAYER 11 — Knowledge Graph
-- =============================================================================

-- Generic typed relationship store — every entity-to-entity relationship
CREATE TABLE IF NOT EXISTS entity_relationships (
    id              BIGSERIAL PRIMARY KEY,
    from_type       TEXT NOT NULL,    -- horse, trainer, jockey, track, race, barrier, condition, sire
    from_id         TEXT NOT NULL,    -- entity identifier (id or slug)
    relationship    TEXT NOT NULL,    -- trained_by, ridden_by, drawn_at, ran_at, ran_in, produced, has_pedigree
    to_type         TEXT NOT NULL,
    to_id           TEXT NOT NULL,
    weight          REAL DEFAULT 1.0, -- relationship strength
    valid_from      TIMESTAMPTZ,
    valid_to        TIMESTAMPTZ,
    properties_json JSONB,            -- additional edge attributes
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_graph_from ON entity_relationships (from_type, from_id, relationship);
CREATE INDEX IF NOT EXISTS idx_graph_to   ON entity_relationships (to_type, to_id, relationship);

-- Log of knowledge graph queries for analytics
CREATE TABLE IF NOT EXISTS graph_query_log (
    id              BIGSERIAL PRIMARY KEY,
    query_text      TEXT NOT NULL,
    executed_at     TIMESTAMPTZ NOT NULL,
    result_count    INTEGER,
    duration_ms     INTEGER,
    tenant_id       INTEGER REFERENCES tenants (id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- LAYER 12 — AI Discovery Engine
-- =============================================================================

-- Nightly discovery job runs
CREATE TABLE IF NOT EXISTS discovery_runs (
    id              SERIAL PRIMARY KEY,
    job_type        TEXT NOT NULL,    -- gate_bias_scan, trainer_trend_scan, sire_trend_scan,
                                      -- market_anomaly_scan, heatmap_pattern_scan,
                                      -- weather_correlation_scan, combination_scan
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running',  -- running, completed, failed
    patterns_found  INTEGER DEFAULT 0,
    signals_emitted INTEGER DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Discovered patterns output
CREATE TABLE IF NOT EXISTS discovered_patterns (
    id              SERIAL PRIMARY KEY,
    pattern_type    TEXT NOT NULL,    -- gate_bias, trainer_trend, sire_trend, market_anomaly,
                                      -- heatmap_correlation, weather_correlation, combination
    description     TEXT NOT NULL,    -- human-readable description of the pattern
    parameters_json JSONB NOT NULL,   -- structured pattern parameters
    roi             REAL,             -- estimated ROI if acted upon
    confidence      REAL NOT NULL,    -- statistical confidence 0–1
    sample_size     INTEGER,
    first_detected  DATE NOT NULL,
    valid_until     DATE,             -- estimated expiry (patterns fade)
    active          BOOLEAN NOT NULL DEFAULT true,
    discovery_run_id INTEGER REFERENCES discovery_runs (id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_patterns_type   ON discovered_patterns (pattern_type, active);
CREATE INDEX IF NOT EXISTS idx_patterns_active ON discovered_patterns (active, valid_until);

-- Generated signals from patterns — applied to specific upcoming races/runners
CREATE TABLE IF NOT EXISTS pattern_signals (
    id              BIGSERIAL PRIMARY KEY,
    pattern_id      INTEGER NOT NULL REFERENCES discovered_patterns (id),
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER REFERENCES race_entries (id),
    signal_strength REAL NOT NULL,    -- 0–1 how strongly this pattern applies
    generated_at    TIMESTAMPTZ NOT NULL,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pattern_signals_race ON pattern_signals (race_id, generated_at DESC);

-- =============================================================================
-- BETMAN PROPRIETARY SCORES
-- =============================================================================

-- Per-horse, per-race score snapshot (computed pre-race)
CREATE TABLE IF NOT EXISTS horse_scores (
    id                      SERIAL PRIMARY KEY,
    race_id                 INTEGER NOT NULL REFERENCES races (id),
    race_entry_id           INTEGER NOT NULL REFERENCES race_entries (id),
    runner_id               INTEGER NOT NULL REFERENCES runners (id),
    -- Individual scores (0–100, NULL if insufficient data)
    bc_score                REAL,  -- BETMAN Confidence
    gas_score               REAL,  -- Gate Advantage Score
    mis_score               REAL,  -- Market Intelligence Score
    sis_score               REAL,  -- Stable Intent Score
    hfs_score               REAL,  -- Heatmap Fitness Score
    was_score               REAL,  -- Weather Affinity Score
    bms_score               REAL,  -- Bloodline Match Score
    tbi_score               REAL,  -- Track Bias Index (runner context)
    value_score             REAL,  -- Value Score
    alpha_score             REAL,  -- Combined Alpha Score
    -- Supporting data at time of calculation
    market_price            NUMERIC,
    implied_probability     REAL,
    betman_probability      REAL,
    -- Metadata
    calculated_at           TIMESTAMPTZ NOT NULL,
    model_version           TEXT,
    UNIQUE (race_id, race_entry_id)
);
CREATE INDEX IF NOT EXISTS idx_horse_scores_race   ON horse_scores (race_id);
CREATE INDEX IF NOT EXISTS idx_horse_scores_runner ON horse_scores (runner_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_horse_scores_alpha  ON horse_scores (race_id, alpha_score DESC NULLS LAST);

-- Historical score archive — scores are updated as race approaches; archive old versions
CREATE TABLE IF NOT EXISTS score_history (
    id              BIGSERIAL PRIMARY KEY,
    horse_score_id  INTEGER NOT NULL REFERENCES horse_scores (id),
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    alpha_score     REAL,
    market_price    NUMERIC,
    snapshot_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_score_history_race ON score_history (race_id, snapshot_at DESC);

-- =============================================================================
-- BETMAN PLATFORM API INTEGRATION
-- =============================================================================

-- API contracts published to BETMAN platform consumers
-- (other BETMAN services authenticate as tenants with is_admin=true)
CREATE TABLE IF NOT EXISTS platform_api_subscriptions (
    id              SERIAL PRIMARY KEY,
    service_name    TEXT UNIQUE NOT NULL,  -- betman_core, betman_web, betman_mobile, betman_algo
    api_key_id      INTEGER NOT NULL REFERENCES tenant_api_keys (id),
    subscribed_events TEXT[],              -- which event types this service receives
    webhook_url     TEXT,                  -- optional push endpoint for events
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- ADDITIONAL INDEXES FOR INTELLIGENCE QUERY PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_fixed_ticks_time    ON fixed_odds_ticks (race_id, time_to_jump_s DESC);
CREATE INDEX IF NOT EXISTS idx_behaviour_attribute ON behaviour_observations (runner_id, attribute, stage);
CREATE INDEX IF NOT EXISTS idx_entity_rel_compound ON entity_relationships (from_type, from_id, to_type);
CREATE INDEX IF NOT EXISTS idx_discovered_roi      ON discovered_patterns (roi DESC NULLS LAST) WHERE active = true;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (version) VALUES ('002_intelligence_layers.sql')
ON CONFLICT (version) DO NOTHING;
