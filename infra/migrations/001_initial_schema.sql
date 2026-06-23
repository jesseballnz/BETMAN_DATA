-- =============================================================================
-- BETMAN_DATA — Initial Schema Migration
-- 001_initial_schema.sql
--
-- Apply with:
--   psql $DATABASE_URL -f infra/migrations/001_initial_schema.sql
--
-- This migration is idempotent (CREATE TABLE IF NOT EXISTS, etc.).
-- Never modify this file — add a new numbered migration for schema changes.
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector: embedding similarity search
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- trigram: fast LIKE/ILIKE search on text fields

-- =============================================================================
-- DOMAIN 1: Racing Entities
-- =============================================================================

-- Race class normalisation — the source of truth for class filtering
CREATE TABLE IF NOT EXISTS race_classes (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,  -- G1, G2, G3, L, R75, MDN, BM65, 2YO, etc.
    "group"     TEXT NOT NULL,         -- group, listed, rating_band, benchmark, maiden, open, age_restricted
    rank        INTEGER,               -- sortable hierarchy: lower = more prestigious
    description TEXT
);

CREATE TABLE IF NOT EXISTS meetings (
    id                  SERIAL PRIMARY KEY,
    external_meeting_id TEXT,
    track_name          TEXT NOT NULL,
    meeting_date        DATE NOT NULL,
    surface             TEXT,          -- turf, synthetic, harness, greyhound
    jurisdiction        TEXT,          -- NZ, AU, etc.
    status              TEXT NOT NULL DEFAULT 'scheduled', -- scheduled, abandoned, completed
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_meetings_date     ON meetings (meeting_date);
CREATE INDEX IF NOT EXISTS idx_meetings_track    ON meetings (track_name);

CREATE TABLE IF NOT EXISTS runners (
    id                 SERIAL PRIMARY KEY,
    external_runner_id TEXT,
    name               TEXT NOT NULL,
    type               TEXT,           -- thoroughbred, harness, greyhound
    country_of_origin  TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_runners_name ON runners USING gin (name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS races (
    id                    SERIAL PRIMARY KEY,
    meeting_id            INTEGER NOT NULL REFERENCES meetings (id),
    external_race_id      TEXT,
    race_number           INTEGER NOT NULL,
    name                  TEXT,
    distance_m            INTEGER,
    scheduled_start_time  TIMESTAMPTZ,
    actual_start_time     TIMESTAMPTZ,
    race_class_id         INTEGER REFERENCES race_classes (id),
    race_class_code       TEXT,        -- denormalised for fast filtering
    race_class_group      TEXT,        -- denormalised
    prize_money           NUMERIC,
    surface               TEXT,        -- overrides meeting surface if set
    status                TEXT NOT NULL DEFAULT 'scheduled', -- scheduled, running, finished, abandoned
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_races_meeting        ON races (meeting_id);
CREATE INDEX IF NOT EXISTS idx_races_class_code     ON races (race_class_code);
CREATE INDEX IF NOT EXISTS idx_races_status         ON races (status);
CREATE INDEX IF NOT EXISTS idx_races_scheduled_start ON races (scheduled_start_time);

CREATE TABLE IF NOT EXISTS race_entries (
    id                SERIAL PRIMARY KEY,
    race_id           INTEGER NOT NULL REFERENCES races (id),
    runner_id         INTEGER NOT NULL REFERENCES runners (id),
    barrier_number    INTEGER,
    saddle_cloth      TEXT,
    jockey_or_driver  TEXT,
    trainer           TEXT,
    weight_kg         NUMERIC,
    scratched         BOOLEAN NOT NULL DEFAULT false,
    final_position    INTEGER,         -- populated post-race
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_race_entries_race   ON race_entries (race_id);
CREATE INDEX IF NOT EXISTS idx_race_entries_runner ON race_entries (runner_id);

-- =============================================================================
-- DOMAIN 2: Feed / Media Entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS feeds (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,          -- Trackside 1, Trackside 2
    url        TEXT NOT NULL,          -- HLS master playlist URL
    active     BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stream_sessions (
    id                    SERIAL PRIMARY KEY,
    feed_id               INTEGER NOT NULL REFERENCES feeds (id),
    started_at            TIMESTAMPTZ NOT NULL,
    ended_at              TIMESTAMPTZ,
    status                TEXT NOT NULL DEFAULT 'active', -- active, ended, error
    selected_rendition_url TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_stream_sessions_feed ON stream_sessions (feed_id);

CREATE TABLE IF NOT EXISTS media_segments (
    id                 BIGSERIAL PRIMARY KEY,
    feed_id            INTEGER NOT NULL REFERENCES feeds (id),
    stream_session_id  INTEGER NOT NULL REFERENCES stream_sessions (id),
    sequence_number    BIGINT NOT NULL,
    segment_started_at TIMESTAMPTZ NOT NULL,
    segment_ended_at   TIMESTAMPTZ NOT NULL,
    duration_ms        INTEGER NOT NULL,
    storage_uri        TEXT NOT NULL,
    content_hash       TEXT,           -- SHA-256, used for dedup
    codec              TEXT,           -- h264, h265
    resolution         TEXT,           -- 1920x1080
    bitrate            INTEGER,        -- bps
    audio_codec        TEXT,           -- aac, opus
    processing_status  TEXT NOT NULL DEFAULT 'pending', -- pending, processing, done, error
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_segments_feed          ON media_segments (feed_id);
CREATE INDEX IF NOT EXISTS idx_segments_session       ON media_segments (stream_session_id);
CREATE INDEX IF NOT EXISTS idx_segments_started_at    ON media_segments (segment_started_at);
CREATE INDEX IF NOT EXISTS idx_segments_proc_status   ON media_segments (processing_status);

CREATE TABLE IF NOT EXISTS audio_chunks (
    id          BIGSERIAL PRIMARY KEY,
    segment_id  BIGINT NOT NULL REFERENCES media_segments (id),
    started_at  TIMESTAMPTZ NOT NULL,
    ended_at    TIMESTAMPTZ NOT NULL,
    duration_ms INTEGER NOT NULL,
    storage_uri TEXT NOT NULL,
    codec       TEXT,                  -- opus, aac
    sample_rate INTEGER,               -- Hz
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audio_chunks_segment ON audio_chunks (segment_id);

CREATE TABLE IF NOT EXISTS keyframes (
    id               BIGSERIAL PRIMARY KEY,
    segment_id       BIGINT NOT NULL REFERENCES media_segments (id),
    frame_timestamp  TIMESTAMPTZ NOT NULL,
    offset_ms        INTEGER NOT NULL,
    storage_uri      TEXT NOT NULL,
    width            INTEGER,
    height           INTEGER,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_keyframes_segment   ON keyframes (segment_id);
CREATE INDEX IF NOT EXISTS idx_keyframes_timestamp ON keyframes (frame_timestamp);

CREATE TABLE IF NOT EXISTS clips (
    id          SERIAL PRIMARY KEY,
    feed_id     INTEGER NOT NULL REFERENCES feeds (id),
    race_id     INTEGER REFERENCES races (id),
    clip_type   TEXT NOT NULL,         -- pre_start, barrier_load, race_live, finish, result, highlight
    started_at  TIMESTAMPTZ NOT NULL,
    ended_at    TIMESTAMPTZ NOT NULL,
    duration_ms INTEGER NOT NULL,
    storage_uri TEXT NOT NULL,
    codec       TEXT,
    resolution  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_clips_race ON clips (race_id);

-- =============================================================================
-- DOMAIN 3: Signal / Observation Entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS ocr_observations (
    id               BIGSERIAL PRIMARY KEY,
    segment_id       BIGINT NOT NULL REFERENCES media_segments (id),
    keyframe_id      BIGINT REFERENCES keyframes (id),
    frame_timestamp  TIMESTAMPTZ NOT NULL,
    detected_text    TEXT NOT NULL,
    normalized_text  TEXT,
    observation_type TEXT,             -- race_number, runner_name, odds, clock, lower_third, tote, unknown
    confidence       REAL,             -- 0-1
    bbox_json        JSONB,            -- {x, y, w, h} bounding box
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ocr_segment    ON ocr_observations (segment_id);
CREATE INDEX IF NOT EXISTS idx_ocr_timestamp  ON ocr_observations (frame_timestamp);
CREATE INDEX IF NOT EXISTS idx_ocr_type       ON ocr_observations (observation_type);
CREATE INDEX IF NOT EXISTS idx_ocr_text_trgm  ON ocr_observations USING gin (normalized_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS audio_events (
    id             BIGSERIAL PRIMARY KEY,
    segment_id     BIGINT NOT NULL REFERENCES media_segments (id),
    audio_chunk_id BIGINT REFERENCES audio_chunks (id),
    started_at     TIMESTAMPTZ NOT NULL,
    ended_at       TIMESTAMPTZ NOT NULL,
    event_type     TEXT NOT NULL,      -- commentary, advertisement, parade_ring, pre_start_build,
                                       -- race_call, result_read, ambient, silence, unknown
    confidence     REAL,
    model_version  TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audio_events_segment    ON audio_events (segment_id);
CREATE INDEX IF NOT EXISTS idx_audio_events_started_at ON audio_events (started_at);
CREATE INDEX IF NOT EXISTS idx_audio_events_type       ON audio_events (event_type);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id             BIGSERIAL PRIMARY KEY,
    audio_event_id BIGINT REFERENCES audio_events (id),
    race_id        INTEGER REFERENCES races (id),  -- resolved after entity matching
    race_offset_ms INTEGER,                        -- ms from actual_start_time (negative = pre-race)
    started_at     TIMESTAMPTZ NOT NULL,
    ended_at       TIMESTAMPTZ NOT NULL,
    text           TEXT NOT NULL,
    language       TEXT NOT NULL DEFAULT 'en',
    confidence     REAL,
    model_version  TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_transcript_race       ON transcript_segments (race_id);
CREATE INDEX IF NOT EXISTS idx_transcript_offset     ON transcript_segments (race_id, race_offset_ms);
CREATE INDEX IF NOT EXISTS idx_transcript_text_trgm  ON transcript_segments USING gin (text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS event_predictions (
    id           SERIAL PRIMARY KEY,
    race_id      INTEGER REFERENCES races (id),
    feed_id      INTEGER NOT NULL REFERENCES feeds (id),
    event_type   TEXT NOT NULL,        -- parade_ring_started, barriers_loading, jump_imminent,
                                       -- race_live, finish_detected, result_announced
    predicted_at TIMESTAMPTZ NOT NULL,
    confidence   REAL,
    source_type  TEXT,                 -- audio, ocr, combined
    source_ids   INTEGER[],
    payload_json JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_event_pred_race ON event_predictions (race_id);
CREATE INDEX IF NOT EXISTS idx_event_pred_type ON event_predictions (event_type);

CREATE TABLE IF NOT EXISTS race_timeline_events (
    id          SERIAL PRIMARY KEY,
    race_id     INTEGER NOT NULL REFERENCES races (id),
    event_type  TEXT NOT NULL,         -- scheduled_start, actual_start, finish, result_official,
                                       -- abandoned, scratching, protest
    event_time  TIMESTAMPTZ NOT NULL,
    source_type TEXT,                  -- feed_data, ocr, audio, manual
    source_id   INTEGER,
    confidence  REAL,
    payload_json JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_timeline_race ON race_timeline_events (race_id);
CREATE INDEX IF NOT EXISTS idx_timeline_time ON race_timeline_events (race_id, event_time);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER REFERENCES race_entries (id),
    captured_at     TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,     -- ocr_tote, api_feed, manual
    win_price       NUMERIC,
    place_price     NUMERIC,
    win_sp          NUMERIC,           -- starting price win
    place_sp        NUMERIC,           -- starting price place
    market_status   TEXT,              -- open, suspended, closed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_odds_race        ON odds_snapshots (race_id);
CREATE INDEX IF NOT EXISTS idx_odds_entry       ON odds_snapshots (race_entry_id);
CREATE INDEX IF NOT EXISTS idx_odds_captured_at ON odds_snapshots (race_id, captured_at);

-- =============================================================================
-- DOMAIN 4: Intelligence Entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS scene_classifications (
    id            BIGSERIAL PRIMARY KEY,
    keyframe_id   BIGINT NOT NULL REFERENCES keyframes (id),
    scene_type    TEXT NOT NULL,       -- studio, parade_ring, mounting_yard, barriers,
                                       -- live_race, finish, replay, advertisement, interview
    confidence    REAL,
    model_version TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scene_keyframe ON scene_classifications (keyframe_id);
CREATE INDEX IF NOT EXISTS idx_scene_type     ON scene_classifications (scene_type);

CREATE TABLE IF NOT EXISTS excitement_scores (
    id              BIGSERIAL PRIMARY KEY,
    audio_event_id  BIGINT NOT NULL REFERENCES audio_events (id),
    race_id         INTEGER REFERENCES races (id),
    race_offset_ms  INTEGER,
    score           REAL NOT NULL,     -- 0-1 excitement level
    peak            BOOLEAN NOT NULL DEFAULT false,
    model_version   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_excitement_race   ON excitement_scores (race_id);
CREATE INDEX IF NOT EXISTS idx_excitement_offset ON excitement_scores (race_id, race_offset_ms);

CREATE TABLE IF NOT EXISTS commentary_entities (
    id                    BIGSERIAL PRIMARY KEY,
    transcript_segment_id BIGINT NOT NULL REFERENCES transcript_segments (id),
    entity_type           TEXT NOT NULL, -- runner_name, position_call, distance_call, race_signal, jockey_name
    raw_text              TEXT NOT NULL,
    normalized_value      TEXT,
    runner_id             INTEGER REFERENCES runners (id),
    position              INTEGER,        -- resolved race position if entity_type = position_call
    confidence            REAL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_comm_entities_transcript ON commentary_entities (transcript_segment_id);
CREATE INDEX IF NOT EXISTS idx_comm_entities_type       ON commentary_entities (entity_type);
CREATE INDEX IF NOT EXISTS idx_comm_entities_runner     ON commentary_entities (runner_id);

CREATE TABLE IF NOT EXISTS race_summaries (
    id                  SERIAL PRIMARY KEY,
    race_id             INTEGER UNIQUE NOT NULL REFERENCES races (id),
    summary_text        TEXT NOT NULL,
    key_moments         JSONB,         -- [{offset_ms, text, type}]
    winner_name         TEXT,
    margin_description  TEXT,          -- "a head", "two lengths"
    model_version       TEXT,
    generated_at        TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- pgvector: vector embeddings for similarity search
-- Requires CREATE EXTENSION vector; (see top of file)
CREATE TABLE IF NOT EXISTS runner_embeddings (
    id              SERIAL PRIMARY KEY,
    subject_type    TEXT NOT NULL,     -- runner, race, audio_window
    subject_id      INTEGER NOT NULL,
    embedding_type  TEXT NOT NULL,     -- visual, audio, commentary, combined
    embedding       vector(1536),      -- OpenAI ada-002 / similar 1536-dim model
    model_version   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IVFFlat index for approximate nearest-neighbour search
CREATE INDEX IF NOT EXISTS idx_embeddings_ivfflat
    ON runner_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_embeddings_subject ON runner_embeddings (subject_type, subject_id);

-- =============================================================================
-- DOMAIN 5: Skin Engine
-- =============================================================================

CREATE TABLE IF NOT EXISTS tenants (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,          -- Ladbrokes, Racing.com, William Hill
    slug                TEXT UNIQUE NOT NULL,   -- ladbrokes, racing-com
    contact_email       TEXT,
    license_type        TEXT NOT NULL DEFAULT 'full', -- full, content_only, odds_only
    license_expires_at  TIMESTAMPTZ,
    active              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- API keys for tenant authentication (hashed, never stored plaintext)
CREATE TABLE IF NOT EXISTS tenant_api_keys (
    id          SERIAL PRIMARY KEY,
    tenant_id   INTEGER NOT NULL REFERENCES tenants (id),
    key_hash    TEXT UNIQUE NOT NULL, -- SHA-256 of the raw API key
    key_prefix  TEXT NOT NULL,        -- first 8 chars of raw key (for UI display)
    label       TEXT,
    is_admin    BOOLEAN NOT NULL DEFAULT false,
    active      BOOLEAN NOT NULL DEFAULT true,
    last_used_at TIMESTAMPTZ,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash     ON tenant_api_keys (key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant   ON tenant_api_keys (tenant_id);

CREATE TABLE IF NOT EXISTS skins (
    id          SERIAL PRIMARY KEY,
    tenant_id   INTEGER NOT NULL REFERENCES tenants (id),
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    is_default  BOOLEAN NOT NULL DEFAULT false,
    active      BOOLEAN NOT NULL DEFAULT true,
    config_json JSONB NOT NULL DEFAULT '{}', -- colors, typography, layout, features
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, slug)
);
CREATE INDEX IF NOT EXISTS idx_skins_tenant ON skins (tenant_id);

CREATE TABLE IF NOT EXISTS skin_contexts (
    id           SERIAL PRIMARY KEY,
    skin_id      INTEGER NOT NULL REFERENCES skins (id),
    context_type TEXT NOT NULL,    -- global, race_class, meeting, race, event
    context_ref  TEXT,             -- e.g. G1, meeting_id, race_id
    priority     INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_skin_contexts_skin ON skin_contexts (skin_id);

CREATE TABLE IF NOT EXISTS skin_assets (
    id          SERIAL PRIMARY KEY,
    skin_id     INTEGER NOT NULL REFERENCES skins (id),
    asset_type  TEXT NOT NULL,    -- logo, logo_dark, favicon, background, sponsor_logo, watermark, ad_creative
    label       TEXT,
    storage_uri TEXT NOT NULL,
    cdn_url     TEXT,
    file_format TEXT,             -- png, svg, webp, jpg
    width       INTEGER,
    height      INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_skin_assets_skin ON skin_assets (skin_id);

CREATE TABLE IF NOT EXISTS ad_slot_types (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL, -- replay_overlay_top, pre_race_banner, results_sidebar, etc.
    description     TEXT,
    dimensions      TEXT,                 -- 728x90, 300x250
    display_context TEXT                  -- replay, pre_race, results, race_card, live
);

CREATE TABLE IF NOT EXISTS ad_placements (
    id            SERIAL PRIMARY KEY,
    skin_id       INTEGER NOT NULL REFERENCES skins (id),
    slot_type_id  INTEGER NOT NULL REFERENCES ad_slot_types (id),
    asset_id      INTEGER REFERENCES skin_assets (id),
    label         TEXT,
    click_url     TEXT,
    active_from   TIMESTAMPTZ,
    active_until  TIMESTAMPTZ,
    priority      INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ad_placements_skin ON ad_placements (skin_id, slot_type_id);

-- Licensed feeds per tenant (with optional override URL per brand)
CREATE TABLE IF NOT EXISTS tenant_feeds (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INTEGER NOT NULL REFERENCES tenants (id),
    feed_id             INTEGER NOT NULL REFERENCES feeds (id),
    override_url        TEXT,             -- custom HLS URL for this tenant
    quality_preference  TEXT NOT NULL DEFAULT 'auto', -- auto, high, medium, low
    active              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, feed_id)
);
CREATE INDEX IF NOT EXISTS idx_tenant_feeds_feed   ON tenant_feeds (feed_id) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_tenant_feeds_tenant ON tenant_feeds (tenant_id);

-- =============================================================================
-- DOMAIN 6: Track Conditions & Weather
-- =============================================================================

-- Encrypted external API key storage (WeatherLink, TAB NZ, odds providers, etc.)
CREATE TABLE IF NOT EXISTS api_key_configs (
    id               SERIAL PRIMARY KEY,
    service_name     TEXT NOT NULL,   -- weatherlink, tab_nz, racing_australia, odds_provider
    key_name         TEXT NOT NULL,
    encrypted_key    TEXT NOT NULL,   -- AES-256 encrypted; decrypted at runtime by Consumer
    endpoint_url     TEXT,
    extra_config_json JSONB DEFAULT '{}',
    active           BOOLEAN NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS weather_stations (
    id                 SERIAL PRIMARY KEY,
    track_name         TEXT NOT NULL,
    station_id         TEXT NOT NULL,  -- WeatherLink station identifier
    api_key_config_id  INTEGER REFERENCES api_key_configs (id),
    label              TEXT,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    elevation_m        REAL,
    active             BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_weather_stations_track ON weather_stations (track_name);

CREATE TABLE IF NOT EXISTS soil_moisture_probes (
    id                      SERIAL PRIMARY KEY,
    station_id              INTEGER NOT NULL REFERENCES weather_stations (id),
    probe_label             TEXT NOT NULL,   -- rail_100m, centre_400m, outside_800m
    position_description    TEXT,
    depth_mm                INTEGER,
    distance_from_finish_m  INTEGER,
    zone                    TEXT,            -- rail, inside, centre, outside
    latitude                DOUBLE PRECISION,
    longitude               DOUBLE PRECISION,
    active                  BOOLEAN NOT NULL DEFAULT true,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_probes_station ON soil_moisture_probes (station_id);

-- High-volume time-series table — partition by month in production
CREATE TABLE IF NOT EXISTS weather_readings (
    id                      BIGSERIAL PRIMARY KEY,
    station_id              INTEGER NOT NULL REFERENCES weather_stations (id),
    recorded_at             TIMESTAMPTZ NOT NULL,
    temperature_c           REAL,
    humidity_pct            REAL,
    wind_speed_kmh          REAL,
    wind_gust_kmh           REAL,
    wind_direction_deg      SMALLINT,
    rainfall_mm             REAL,
    rainfall_1h_mm          REAL,
    rainfall_24h_mm         REAL,
    barometric_pressure_hpa REAL,
    uv_index                REAL,
    solar_radiation_wm2     REAL,
    dew_point_c             REAL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_weather_readings_station ON weather_readings (station_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS soil_moisture_readings (
    id               BIGSERIAL PRIMARY KEY,
    probe_id         INTEGER NOT NULL REFERENCES soil_moisture_probes (id),
    recorded_at      TIMESTAMPTZ NOT NULL,
    moisture_pct     REAL NOT NULL,
    soil_temperature_c REAL,
    raw_value        REAL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_soil_readings_probe ON soil_moisture_readings (probe_id, recorded_at DESC);

-- Official/derived track condition ratings
CREATE TABLE IF NOT EXISTS track_condition_readings (
    id                  SERIAL PRIMARY KEY,
    meeting_id          INTEGER NOT NULL REFERENCES meetings (id),
    race_id             INTEGER REFERENCES races (id),
    condition_code      TEXT NOT NULL,   -- H10, H9, S6, G4, G3, F2, F1, ST
    condition_category  TEXT NOT NULL,   -- heavy, soft, good, firm, synthetic
    penetrometer_value  REAL,
    recorded_at         TIMESTAMPTZ NOT NULL,
    source              TEXT NOT NULL,   -- official, stewards, estimated, weatherlink_derived
    weather_reading_id  INTEGER REFERENCES weather_readings (id),
    avg_soil_moisture_pct REAL,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_track_conditions_meeting ON track_condition_readings (meeting_id);
CREATE INDEX IF NOT EXISTS idx_track_conditions_code    ON track_condition_readings (condition_code);

CREATE TABLE IF NOT EXISTS track_maps (
    id               SERIAL PRIMARY KEY,
    track_name       TEXT NOT NULL,
    surface          TEXT NOT NULL,
    circumference_m  INTEGER,
    straight_m       INTEGER,
    geometry_json    JSONB,   -- GeoJSON track outline
    zones_json       JSONB,   -- [{zone, from_finish_m, to_finish_m, label}]
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (track_name, surface)
);

-- =============================================================================
-- DOMAIN 7: Barrier Analysis
-- =============================================================================

-- Core append-only ledger — one row per race entry after result confirmation
CREATE TABLE IF NOT EXISTS barrier_outcomes (
    id                   BIGSERIAL PRIMARY KEY,
    race_id              INTEGER NOT NULL REFERENCES races (id),
    race_entry_id        INTEGER NOT NULL REFERENCES race_entries (id),
    runner_id            INTEGER NOT NULL REFERENCES runners (id),
    barrier_number       INTEGER NOT NULL,
    field_size           INTEGER NOT NULL,
    relative_barrier     TEXT NOT NULL,   -- inside_third, middle_third, outside_third
    final_position       INTEGER NOT NULL,
    won                  BOOLEAN NOT NULL,
    placed               BOOLEAN NOT NULL,
    unplaced             BOOLEAN NOT NULL,
    margin_lengths       REAL,
    -- Denormalised for fast analytical queries (avoids joins on every query)
    track_name           TEXT NOT NULL,
    surface              TEXT NOT NULL,
    distance_m           INTEGER NOT NULL,
    race_class_code      TEXT,
    race_class_group     TEXT,
    condition_code       TEXT,            -- H10, S6, G4, etc. at race time
    condition_category   TEXT,
    penetrometer_value   REAL,
    avg_soil_moisture_pct REAL,
    temperature_c        REAL,
    humidity_pct         REAL,
    rainfall_24h_mm      REAL,
    race_date            DATE NOT NULL,   -- denormalised for fast date-range queries
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_barrier_outcomes_track     ON barrier_outcomes (track_name, surface);
CREATE INDEX IF NOT EXISTS idx_barrier_outcomes_condition ON barrier_outcomes (track_name, condition_code);
CREATE INDEX IF NOT EXISTS idx_barrier_outcomes_barrier   ON barrier_outcomes (track_name, barrier_number);
CREATE INDEX IF NOT EXISTS idx_barrier_outcomes_date      ON barrier_outcomes (race_date);
CREATE INDEX IF NOT EXISTS idx_barrier_outcomes_race      ON barrier_outcomes (race_id);

-- Pre-computed aggregations — rebuilt after each race result
CREATE TABLE IF NOT EXISTS barrier_statistics (
    id                 SERIAL PRIMARY KEY,
    track_name         TEXT NOT NULL,
    surface            TEXT NOT NULL,
    distance_band      TEXT NOT NULL,     -- 1000-1200, 1200-1400, 1400-1600, 1600-2000, 2000+
    condition_category TEXT NOT NULL,
    condition_code     TEXT,              -- NULL = all codes in category
    field_size_band    TEXT NOT NULL,     -- 1-8, 9-12, 13-16, 17+
    barrier_number     INTEGER NOT NULL,
    relative_barrier   TEXT NOT NULL,
    race_class_group   TEXT,              -- NULL = all classes
    total_runners      INTEGER NOT NULL DEFAULT 0,
    wins               INTEGER NOT NULL DEFAULT 0,
    places             INTEGER NOT NULL DEFAULT 0,
    win_rate           REAL NOT NULL DEFAULT 0,
    place_rate         REAL NOT NULL DEFAULT 0,
    avg_win_price      REAL,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (track_name, surface, distance_band, condition_category, condition_code,
            field_size_band, barrier_number, race_class_group)
);
CREATE INDEX IF NOT EXISTS idx_barrier_stats_lookup
    ON barrier_statistics (track_name, surface, condition_category, condition_code);

-- Spatial heat map cells — rebuilt after each race result
CREATE TABLE IF NOT EXISTS track_heatmap_cells (
    id                        SERIAL PRIMARY KEY,
    track_name                TEXT NOT NULL,
    surface                   TEXT NOT NULL,
    condition_category        TEXT NOT NULL,
    distance_band             TEXT NOT NULL,
    zone                      TEXT NOT NULL,   -- rail, inside, middle, outside
    distance_from_finish_band TEXT,            -- 0-200, 200-400, 400-800, 800+
    win_count                 INTEGER NOT NULL DEFAULT 0,
    place_count               INTEGER NOT NULL DEFAULT 0,
    runner_count              INTEGER NOT NULL DEFAULT 0,
    win_rate                  REAL,
    place_rate                REAL,
    intensity                 REAL,            -- normalised 0-1 for heat map gradient
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (track_name, surface, condition_category, distance_band, zone, distance_from_finish_band)
);

-- =============================================================================
-- DOMAIN 8: Odds Analytics
-- =============================================================================

-- Every detected significant odds movement (streaming from Consumer)
CREATE TABLE IF NOT EXISTS odds_movements (
    id              BIGSERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    race_entry_id   INTEGER NOT NULL REFERENCES race_entries (id),
    detected_at     TIMESTAMPTZ NOT NULL,
    time_to_jump_s  INTEGER,           -- seconds before scheduled start (negative = after)
    from_price      NUMERIC NOT NULL,
    to_price        NUMERIC NOT NULL,
    movement_pct    REAL NOT NULL,     -- negative = firming, positive = drifting
    movement_type   TEXT NOT NULL,     -- steam, firm, drift, blowout, late_firm, market_open, market_suspend
    source          TEXT NOT NULL,     -- api_feed, ocr_tote
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_odds_movements_race    ON odds_movements (race_id);
CREATE INDEX IF NOT EXISTS idx_odds_movements_entry   ON odds_movements (race_entry_id);
CREATE INDEX IF NOT EXISTS idx_odds_movements_type    ON odds_movements (movement_type);
CREATE INDEX IF NOT EXISTS idx_odds_movements_time    ON odds_movements (race_id, detected_at);

-- Pre-computed per-entry summary — updated after each snapshot batch
CREATE TABLE IF NOT EXISTS odds_analytics (
    id                    SERIAL PRIMARY KEY,
    race_id               INTEGER NOT NULL REFERENCES races (id),
    race_entry_id         INTEGER UNIQUE NOT NULL REFERENCES race_entries (id),
    opening_price         NUMERIC,
    closing_price         NUMERIC,
    min_price             NUMERIC,
    max_price             NUMERIC,
    price_range           REAL,
    total_movement_pct    REAL,
    firmings_count        INTEGER NOT NULL DEFAULT 0,
    driftings_count       INTEGER NOT NULL DEFAULT 0,
    steam_detected        BOOLEAN NOT NULL DEFAULT false,
    blowout_detected      BOOLEAN NOT NULL DEFAULT false,
    biggest_move_pct      REAL,
    biggest_move_type     TEXT,
    snapshot_count        INTEGER NOT NULL DEFAULT 0,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_odds_analytics_race ON odds_analytics (race_id);

-- =============================================================================
-- PRODUCTION / OEM
-- =============================================================================

-- Per-tenant API usage tracking for billing and rate limiting
CREATE TABLE IF NOT EXISTS tenant_usage (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   INTEGER NOT NULL REFERENCES tenants (id),
    endpoint    TEXT NOT NULL,
    method      TEXT NOT NULL,
    status_code SMALLINT,
    duration_ms INTEGER,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tenant_usage_tenant ON tenant_usage (tenant_id, captured_at DESC);

-- Audit log for all admin actions
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   INTEGER REFERENCES tenants (id),
    actor       TEXT NOT NULL,      -- API key prefix or "system"
    action      TEXT NOT NULL,      -- tenant.create, skin.update, feed.assign, etc.
    resource    TEXT,               -- e.g. "skins/3"
    payload_json JSONB,
    ip_address  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log (action);

-- =============================================================================
-- SEED DATA
-- =============================================================================

-- Race classes
INSERT INTO race_classes (code, "group", rank, description) VALUES
    ('G1',  'group',        1,  'Group 1'),
    ('G2',  'group',        2,  'Group 2'),
    ('G3',  'group',        3,  'Group 3'),
    ('L',   'listed',       4,  'Listed'),
    ('R90', 'rating_band',  40, 'Rating 90+'),
    ('R80', 'rating_band',  45, 'Rating 80+'),
    ('R75', 'rating_band',  50, 'Rating 75+'),
    ('R65', 'rating_band',  55, 'Rating 65+'),
    ('BM78','benchmark',    58, 'Benchmark 78'),
    ('BM65','benchmark',    60, 'Benchmark 65'),
    ('BM58','benchmark',    62, 'Benchmark 58'),
    ('MDN', 'maiden',       90, 'Maiden'),
    ('2YO', 'age_restricted',80,'Two-year-olds'),
    ('3YO', 'age_restricted',75,'Three-year-olds'),
    ('OPN', 'open',         70, 'Open')
ON CONFLICT (code) DO NOTHING;

-- Default feeds
INSERT INTO feeds (name, url) VALUES
    ('Trackside 1', 'https://trackside-nz.akamaized.net/hls/live/2115595/Trackside1/OnDemand/master.m3u8'),
    ('Trackside 2', 'https://trackside-nz.akamaized.net/hls/live/2115596/Trackside2/OnDemand/master.m3u8')
ON CONFLICT DO NOTHING;

-- Ad slot types
INSERT INTO ad_slot_types (code, description, dimensions, display_context) VALUES
    ('replay_overlay_top',     'Top banner over the replay player',    '970x60',  'replay'),
    ('pre_race_banner',        'Pre-race leaderboard banner',          '728x90',  'pre_race'),
    ('results_sidebar',        'Results page sidebar',                 '300x250', 'results'),
    ('race_card_footer',       'Footer below the race card',           '728x90',  'race_card'),
    ('commentary_interstitial','Full-screen between commentary clips', '640x480', 'replay'),
    ('live_overlay_bug',       'Persistent bug overlay during live',   '120x60',  'live')
ON CONFLICT (code) DO NOTHING;
