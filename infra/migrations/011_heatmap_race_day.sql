\set ON_ERROR_STOP on

-- =============================================================================
-- BETMAN_DATA — Heatmap Race Day capture state
--
-- Race cards remain authoritative in public.meetings/races/race_entries/runners.
-- Heatmap may SELECT those tables and may mutate only this dedicated schema.
-- Frame binaries remain on Heatmap storage; this schema stores indexed metadata.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS heatmap_race_day;

CREATE TABLE IF NOT EXISTS heatmap_race_day.meeting_runs (
    id              BIGSERIAL PRIMARY KEY,
    meeting_id      INTEGER NOT NULL REFERENCES public.meetings (id),
    state           TEXT NOT NULL DEFAULT 'active'
                    CHECK (state IN ('active', 'completed', 'cancelled')),
    selected_by     TEXT NOT NULL,
    selected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_heatmap_race_day_one_active_meeting
    ON heatmap_race_day.meeting_runs ((state)) WHERE state = 'active';
CREATE INDEX IF NOT EXISTS ix_heatmap_race_day_meeting_runs_meeting
    ON heatmap_race_day.meeting_runs (meeting_id, selected_at DESC);

CREATE TABLE IF NOT EXISTS heatmap_race_day.race_runs (
    id                BIGSERIAL PRIMARY KEY,
    meeting_run_id    BIGINT NOT NULL REFERENCES heatmap_race_day.meeting_runs (id) ON DELETE CASCADE,
    race_id           INTEGER NOT NULL REFERENCES public.races (id),
    state             TEXT NOT NULL DEFAULT 'locked'
                      CHECK (state IN ('locked', 'open', 'closing', 'archived', 'archive_failed', 'cancelled')),
    closed_by         TEXT,
    closed_at         TIMESTAMPTZ,
    archive_status    TEXT NOT NULL DEFAULT 'not_requested'
                      CHECK (archive_status IN ('not_requested', 'pending', 'processing', 'complete', 'failed')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (meeting_run_id, race_id)
);
CREATE INDEX IF NOT EXISTS ix_heatmap_race_day_race_runs_queue
    ON heatmap_race_day.race_runs (meeting_run_id, state, race_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_heatmap_race_day_one_open_race
    ON heatmap_race_day.race_runs (meeting_run_id) WHERE state IN ('open', 'closing', 'archive_failed');

CREATE TABLE IF NOT EXISTS heatmap_race_day.runner_scan_sessions (
    id                  BIGSERIAL PRIMARY KEY,
    race_run_id         BIGINT NOT NULL REFERENCES heatmap_race_day.race_runs (id) ON DELETE CASCADE,
    race_entry_id       INTEGER NOT NULL REFERENCES public.race_entries (id),
    runner_id           INTEGER NOT NULL REFERENCES public.runners (id),
    horse_number        TEXT NOT NULL,
    horse_name          TEXT NOT NULL,
    state               TEXT NOT NULL DEFAULT 'awaiting-pre'
                        CHECK (state IN ('awaiting-pre', 'scanning-pre', 'awaiting-post', 'scanning-post', 'complete', 'cancelled')),
    active_phase        TEXT CHECK (active_phase IS NULL OR active_phase IN ('pre', 'post')),
    skip_reason         TEXT,
    pre_started_at      TIMESTAMPTZ,
    pre_completed_at    TIMESTAMPTZ,
    post_started_at     TIMESTAMPTZ,
    post_completed_at   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (race_run_id, race_entry_id)
);
CREATE INDEX IF NOT EXISTS ix_heatmap_race_day_runner_queue
    ON heatmap_race_day.runner_scan_sessions (race_run_id, state, horse_number);
CREATE INDEX IF NOT EXISTS ix_heatmap_race_day_runner_identity
    ON heatmap_race_day.runner_scan_sessions (runner_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_heatmap_race_day_one_active_horse
    ON heatmap_race_day.runner_scan_sessions ((active_phase IS NOT NULL))
    WHERE active_phase IS NOT NULL;

CREATE TABLE IF NOT EXISTS heatmap_race_day.scan_frames (
    id                    BIGSERIAL PRIMARY KEY,
    runner_scan_id        BIGINT NOT NULL REFERENCES heatmap_race_day.runner_scan_sessions (id) ON DELETE CASCADE,
    phase                 TEXT NOT NULL CHECK (phase IN ('pre', 'post')),
    camera_key            TEXT NOT NULL,
    captured_at           TIMESTAMPTZ NOT NULL,
    raw_storage_path      TEXT NOT NULL,
    processed_storage_path TEXT,
    content_sha256        TEXT NOT NULL,
    idempotency_key       TEXT NOT NULL UNIQUE,
    assignment_source     TEXT NOT NULL CHECK (assignment_source IN ('manual', 'ocr')),
    ocr_horse_number      TEXT,
    ocr_confidence        REAL,
    analysis_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_heatmap_race_day_scan_frames_session_phase
    ON heatmap_race_day.scan_frames (runner_scan_id, phase, captured_at DESC);
CREATE INDEX IF NOT EXISTS ix_heatmap_race_day_scan_frames_camera
    ON heatmap_race_day.scan_frames (camera_key, captured_at DESC);

CREATE TABLE IF NOT EXISTS heatmap_race_day.archive_jobs (
    id              BIGSERIAL PRIMARY KEY,
    race_run_id     BIGINT NOT NULL UNIQUE REFERENCES heatmap_race_day.race_runs (id) ON DELETE CASCADE,
    state           TEXT NOT NULL DEFAULT 'pending'
                    CHECK (state IN ('pending', 'processing', 'complete', 'failed')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    manifest_path   TEXT,
    manifest_sha256 TEXT,
    size_bytes      BIGINT,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_heatmap_race_day_archive_queue
    ON heatmap_race_day.archive_jobs (state, created_at);

INSERT INTO schema_migrations (version)
VALUES ('011_heatmap_race_day.sql')
ON CONFLICT (version) DO NOTHING;
