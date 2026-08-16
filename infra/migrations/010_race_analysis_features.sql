\set ON_ERROR_STOP on

-- Deterministic, versioned input package for every eligible runner.
CREATE TABLE IF NOT EXISTS race_analysis_features (
    id                  BIGSERIAL PRIMARY KEY,
    race_id             INTEGER NOT NULL REFERENCES races (id),
    race_entry_id       INTEGER NOT NULL REFERENCES race_entries (id),
    runner_id           INTEGER NOT NULL REFERENCES runners (id),
    generated_at        TIMESTAMPTZ NOT NULL,
    source_cutoff_at    TIMESTAMPTZ NOT NULL,
    feature_version     TEXT NOT NULL,
    feature_vector      JSONB NOT NULL,
    provenance          JSONB NOT NULL DEFAULT '{}'::jsonb,
    missing_features    JSONB NOT NULL DEFAULT '[]'::jsonb,
    market_price        NUMERIC,
    market_probability  REAL,
    model_probability   REAL,
    fair_odds           REAL,
    edge                REAL,
    confidence          REAL,
    UNIQUE (race_id, race_entry_id, feature_version)
);
CREATE INDEX IF NOT EXISTS idx_analysis_features_race
    ON race_analysis_features (race_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_features_runner
    ON race_analysis_features (runner_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS race_prediction_snapshots (
    id                  BIGSERIAL PRIMARY KEY,
    race_id             INTEGER NOT NULL REFERENCES races (id),
    race_entry_id       INTEGER NOT NULL REFERENCES race_entries (id),
    generated_at        TIMESTAMPTZ NOT NULL,
    model_version       TEXT NOT NULL,
    probability         REAL NOT NULL CHECK (probability >= 0 AND probability <= 1),
    fair_odds           REAL,
    market_price        NUMERIC,
    edge                REAL,
    stake_fraction      REAL CHECK (stake_fraction >= 0 AND stake_fraction <= 1),
    outcome_position    INTEGER,
    outcome_recorded_at TIMESTAMPTZ,
    brier_score         REAL,
    log_loss            REAL,
    roi                 REAL
);
CREATE INDEX IF NOT EXISTS idx_prediction_snapshots_race
    ON race_prediction_snapshots (race_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_snapshots_model
    ON race_prediction_snapshots (model_version, generated_at DESC);

INSERT INTO schema_migrations (version) VALUES ('010_race_analysis_features.sql')
ON CONFLICT (version) DO NOTHING;
