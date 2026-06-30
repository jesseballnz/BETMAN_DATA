\set ON_ERROR_STOP on

-- BETMAN_DATA retention policy for storage-constrained production hosts.
--
-- Keeps race/meeting/runner/result metadata and prunes high-frequency fact
-- tables that are regenerated continuously. Deletes are intentionally batched
-- so retention can run safely on production without long exclusive pressure.
\if :{?high_frequency_retention_days}
\else
  \set high_frequency_retention_days 7
\endif
\if :{?smart_money_retention_days}
\else
  \set smart_money_retention_days 2
\endif
\if :{?prune_batch_size}
\else
  \set prune_batch_size 5000
\endif
\if :{?prune_max_batches}
\else
  \set prune_max_batches 100
\endif

SELECT pg_advisory_lock(hashtext('betman_data_retention_prune'));

\timing on

SET statement_timeout = 0;
SET lock_timeout = '5s';

SELECT
    current_date AS today,
    current_date - (:high_frequency_retention_days::int * interval '1 day') AS high_frequency_cutoff,
    current_date - (:smart_money_retention_days::int * interval '1 day') AS smart_money_cutoff,
    :prune_batch_size::int AS prune_batch_size,
    :prune_max_batches::int AS prune_max_batches;

-- Dedicated prune index. Existing smart-money indexes lead with confidence or
-- race_entry_id, so they do not help retention scans by detected_at. BRIN keeps
-- this cheap on the 100GB+ append-heavy smart money table.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_smart_money_detected_at_prune
    ON smart_money_indicators USING brin (detected_at) WITH (pages_per_range = 128);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_market_signals_detected_at_prune
    ON market_signals USING brin (detected_at) WITH (pages_per_range = 128);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_odds_snapshots_captured_at_prune
    ON odds_snapshots USING brin (captured_at) WITH (pages_per_range = 128);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fixed_odds_ticks_captured_at_prune
    ON fixed_odds_ticks USING brin (captured_at) WITH (pages_per_range = 128);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tote_pools_captured_at_prune
    ON tote_pools USING brin (captured_at) WITH (pages_per_range = 128);

CREATE TABLE IF NOT EXISTS smart_money_daily_summary (
    summary_date date NOT NULL,
    race_id integer NOT NULL,
    race_entry_id integer NOT NULL,
    indicator_type text NOT NULL,
    indicator_count bigint NOT NULL DEFAULT 0,
    confidence_sum double precision NOT NULL DEFAULT 0,
    max_confidence real,
    first_detected_at timestamptz,
    last_detected_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (summary_date, race_id, race_entry_id, indicator_type)
);

CREATE TABLE IF NOT EXISTS market_signal_daily_summary (
    summary_date date NOT NULL,
    race_id integer NOT NULL,
    race_entry_id integer NOT NULL DEFAULT 0,
    signal_type text NOT NULL,
    signal_count bigint NOT NULL DEFAULT 0,
    magnitude_sum double precision NOT NULL DEFAULT 0,
    max_magnitude real,
    first_detected_at timestamptz,
    last_detected_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (summary_date, race_id, race_entry_id, signal_type)
);

CREATE TABLE IF NOT EXISTS odds_snapshot_daily_summary (
    summary_date date NOT NULL,
    race_id integer NOT NULL,
    race_entry_id integer NOT NULL,
    source text NOT NULL,
    market_status text NOT NULL DEFAULT '',
    snapshot_count bigint NOT NULL DEFAULT 0,
    win_price_sum numeric NOT NULL DEFAULT 0,
    win_price_count bigint NOT NULL DEFAULT 0,
    place_price_sum numeric NOT NULL DEFAULT 0,
    place_price_count bigint NOT NULL DEFAULT 0,
    min_win_price numeric,
    max_win_price numeric,
    last_win_price numeric,
    min_place_price numeric,
    max_place_price numeric,
    last_place_price numeric,
    first_captured_at timestamptz,
    last_captured_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (summary_date, race_id, race_entry_id, source, market_status)
);

CREATE TABLE IF NOT EXISTS fixed_odds_tick_daily_summary (
    summary_date date NOT NULL,
    race_id integer NOT NULL,
    race_entry_id integer NOT NULL,
    source text NOT NULL,
    tick_count bigint NOT NULL DEFAULT 0,
    price_sum numeric NOT NULL DEFAULT 0,
    price_count bigint NOT NULL DEFAULT 0,
    min_price numeric,
    max_price numeric,
    last_price numeric,
    first_captured_at timestamptz,
    last_captured_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (summary_date, race_id, race_entry_id, source)
);

CREATE TABLE IF NOT EXISTS tote_pool_daily_summary (
    summary_date date NOT NULL,
    race_id integer NOT NULL,
    pool_type text NOT NULL,
    sample_count bigint NOT NULL DEFAULT 0,
    pool_size_sum numeric NOT NULL DEFAULT 0,
    pool_size_count bigint NOT NULL DEFAULT 0,
    max_pool_size numeric,
    last_pool_size numeric,
    dividend_sum numeric NOT NULL DEFAULT 0,
    dividend_count bigint NOT NULL DEFAULT 0,
    first_captured_at timestamptz,
    last_captured_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (summary_date, race_id, pool_type)
);

GRANT SELECT ON
    smart_money_daily_summary,
    market_signal_daily_summary,
    odds_snapshot_daily_summary,
    fixed_odds_tick_daily_summary,
    tote_pool_daily_summary
TO betman_data;

CREATE TEMP TABLE retention_prune_results (
    metric text PRIMARY KEY,
    rows_deleted bigint NOT NULL
) ON COMMIT PRESERVE ROWS;

CREATE OR REPLACE FUNCTION pg_temp.prune_smart_money(
    cutoff timestamptz,
    batch_size int,
    max_batches int
) RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    total_deleted bigint := 0;
    batch_deleted bigint := 0;
    batch_number int := 0;
BEGIN
    LOOP
        EXIT WHEN batch_number >= max_batches;

        CREATE TEMP TABLE doomed_smart_money ON COMMIT DROP AS
        SELECT ctid AS row_ctid, race_id, race_entry_id, indicator_type, confidence, detected_at
        FROM smart_money_indicators
        WHERE detected_at < cutoff
        LIMIT batch_size;

        SELECT COUNT(*) INTO batch_deleted FROM doomed_smart_money;
        EXIT WHEN batch_deleted = 0;

        INSERT INTO smart_money_daily_summary (
            summary_date, race_id, race_entry_id, indicator_type, indicator_count,
            confidence_sum, max_confidence, first_detected_at, last_detected_at
        )
        SELECT detected_at::date, race_id, race_entry_id, indicator_type, COUNT(*),
            SUM(confidence), MAX(confidence), MIN(detected_at), MAX(detected_at)
        FROM doomed_smart_money
        GROUP BY detected_at::date, race_id, race_entry_id, indicator_type
        ON CONFLICT (summary_date, race_id, race_entry_id, indicator_type) DO UPDATE
        SET indicator_count = smart_money_daily_summary.indicator_count + EXCLUDED.indicator_count,
            confidence_sum = smart_money_daily_summary.confidence_sum + EXCLUDED.confidence_sum,
            max_confidence = GREATEST(smart_money_daily_summary.max_confidence, EXCLUDED.max_confidence),
            first_detected_at = LEAST(smart_money_daily_summary.first_detected_at, EXCLUDED.first_detected_at),
            last_detected_at = GREATEST(smart_money_daily_summary.last_detected_at, EXCLUDED.last_detected_at),
            updated_at = now();

        DELETE FROM smart_money_indicators t USING doomed_smart_money d WHERE t.ctid = d.row_ctid;

        total_deleted := total_deleted + batch_deleted;
        batch_number := batch_number + 1;
        DROP TABLE doomed_smart_money;

        EXIT WHEN batch_deleted < batch_size;
    END LOOP;

    RETURN total_deleted;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp.prune_market_signals(
    cutoff timestamptz,
    batch_size int,
    max_batches int
) RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    total_deleted bigint := 0;
    batch_deleted bigint := 0;
    batch_number int := 0;
BEGIN
    LOOP
        EXIT WHEN batch_number >= max_batches;
        CREATE TEMP TABLE doomed_market_signals ON COMMIT DROP AS
        SELECT ctid AS row_ctid, race_id, COALESCE(race_entry_id, 0) AS race_entry_id, signal_type, magnitude, detected_at
        FROM market_signals
        WHERE detected_at < cutoff
        LIMIT batch_size;
        SELECT COUNT(*) INTO batch_deleted FROM doomed_market_signals;
        EXIT WHEN batch_deleted = 0;

        INSERT INTO market_signal_daily_summary (
            summary_date, race_id, race_entry_id, signal_type, signal_count,
            magnitude_sum, max_magnitude, first_detected_at, last_detected_at
        )
        SELECT detected_at::date, race_id, race_entry_id, signal_type, COUNT(*),
            SUM(magnitude), MAX(magnitude), MIN(detected_at), MAX(detected_at)
        FROM doomed_market_signals
        GROUP BY detected_at::date, race_id, race_entry_id, signal_type
        ON CONFLICT (summary_date, race_id, race_entry_id, signal_type) DO UPDATE
        SET signal_count = market_signal_daily_summary.signal_count + EXCLUDED.signal_count,
            magnitude_sum = market_signal_daily_summary.magnitude_sum + EXCLUDED.magnitude_sum,
            max_magnitude = GREATEST(market_signal_daily_summary.max_magnitude, EXCLUDED.max_magnitude),
            first_detected_at = LEAST(market_signal_daily_summary.first_detected_at, EXCLUDED.first_detected_at),
            last_detected_at = GREATEST(market_signal_daily_summary.last_detected_at, EXCLUDED.last_detected_at),
            updated_at = now();

        DELETE FROM market_signals t USING doomed_market_signals d WHERE t.ctid = d.row_ctid;
        total_deleted := total_deleted + batch_deleted;
        batch_number := batch_number + 1;
        DROP TABLE doomed_market_signals;
        EXIT WHEN batch_deleted < batch_size;
    END LOOP;
    RETURN total_deleted;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp.prune_odds_snapshots(
    cutoff timestamptz,
    batch_size int,
    max_batches int
) RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    total_deleted bigint := 0;
    batch_deleted bigint := 0;
    batch_number int := 0;
BEGIN
    LOOP
        EXIT WHEN batch_number >= max_batches;
        CREATE TEMP TABLE doomed_odds_snapshots ON COMMIT DROP AS
        SELECT ctid AS row_ctid, race_id, race_entry_id, captured_at, source, COALESCE(market_status, '') AS market_status,
            win_price, place_price
        FROM odds_snapshots
        WHERE captured_at < cutoff
        LIMIT batch_size;
        SELECT COUNT(*) INTO batch_deleted FROM doomed_odds_snapshots;
        EXIT WHEN batch_deleted = 0;

        INSERT INTO odds_snapshot_daily_summary (
            summary_date, race_id, race_entry_id, source, market_status, snapshot_count,
            win_price_sum, win_price_count, place_price_sum, place_price_count,
            min_win_price, max_win_price, last_win_price, min_place_price, max_place_price,
            last_place_price, first_captured_at, last_captured_at
        )
        SELECT DISTINCT ON (summary_date, race_id, race_entry_id, source, market_status)
            captured_at::date AS summary_date, race_id, race_entry_id, source, market_status,
            COUNT(*) OVER w AS snapshot_count,
            COALESCE(SUM(win_price) FILTER (WHERE win_price IS NOT NULL) OVER w, 0) AS win_price_sum,
            COUNT(win_price) OVER w AS win_price_count,
            COALESCE(SUM(place_price) FILTER (WHERE place_price IS NOT NULL) OVER w, 0) AS place_price_sum,
            COUNT(place_price) OVER w AS place_price_count,
            MIN(win_price) OVER w AS min_win_price,
            MAX(win_price) OVER w AS max_win_price,
            FIRST_VALUE(win_price) OVER w_desc AS last_win_price,
            MIN(place_price) OVER w AS min_place_price,
            MAX(place_price) OVER w AS max_place_price,
            FIRST_VALUE(place_price) OVER w_desc AS last_place_price,
            MIN(captured_at) OVER w AS first_captured_at,
            MAX(captured_at) OVER w AS last_captured_at
        FROM doomed_odds_snapshots
        WINDOW
            w AS (PARTITION BY captured_at::date, race_id, race_entry_id, source, market_status),
            w_desc AS (PARTITION BY captured_at::date, race_id, race_entry_id, source, market_status ORDER BY captured_at DESC)
        ORDER BY summary_date, race_id, race_entry_id, source, market_status, last_captured_at DESC
        ON CONFLICT (summary_date, race_id, race_entry_id, source, market_status) DO UPDATE
        SET snapshot_count = odds_snapshot_daily_summary.snapshot_count + EXCLUDED.snapshot_count,
            win_price_sum = odds_snapshot_daily_summary.win_price_sum + EXCLUDED.win_price_sum,
            win_price_count = odds_snapshot_daily_summary.win_price_count + EXCLUDED.win_price_count,
            place_price_sum = odds_snapshot_daily_summary.place_price_sum + EXCLUDED.place_price_sum,
            place_price_count = odds_snapshot_daily_summary.place_price_count + EXCLUDED.place_price_count,
            min_win_price = LEAST(odds_snapshot_daily_summary.min_win_price, EXCLUDED.min_win_price),
            max_win_price = GREATEST(odds_snapshot_daily_summary.max_win_price, EXCLUDED.max_win_price),
            last_win_price = CASE WHEN EXCLUDED.last_captured_at >= odds_snapshot_daily_summary.last_captured_at THEN EXCLUDED.last_win_price ELSE odds_snapshot_daily_summary.last_win_price END,
            min_place_price = LEAST(odds_snapshot_daily_summary.min_place_price, EXCLUDED.min_place_price),
            max_place_price = GREATEST(odds_snapshot_daily_summary.max_place_price, EXCLUDED.max_place_price),
            last_place_price = CASE WHEN EXCLUDED.last_captured_at >= odds_snapshot_daily_summary.last_captured_at THEN EXCLUDED.last_place_price ELSE odds_snapshot_daily_summary.last_place_price END,
            first_captured_at = LEAST(odds_snapshot_daily_summary.first_captured_at, EXCLUDED.first_captured_at),
            last_captured_at = GREATEST(odds_snapshot_daily_summary.last_captured_at, EXCLUDED.last_captured_at),
            updated_at = now();

        DELETE FROM odds_snapshots t USING doomed_odds_snapshots d WHERE t.ctid = d.row_ctid;
        total_deleted := total_deleted + batch_deleted;
        batch_number := batch_number + 1;
        DROP TABLE doomed_odds_snapshots;
        EXIT WHEN batch_deleted < batch_size;
    END LOOP;
    RETURN total_deleted;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp.prune_fixed_odds_ticks(
    cutoff timestamptz,
    batch_size int,
    max_batches int
) RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    total_deleted bigint := 0;
    batch_deleted bigint := 0;
    batch_number int := 0;
BEGIN
    LOOP
        EXIT WHEN batch_number >= max_batches;
        CREATE TEMP TABLE doomed_fixed_odds_ticks ON COMMIT DROP AS
        SELECT ctid AS row_ctid, race_id, race_entry_id, captured_at, source, price
        FROM fixed_odds_ticks
        WHERE captured_at < cutoff
        LIMIT batch_size;
        SELECT COUNT(*) INTO batch_deleted FROM doomed_fixed_odds_ticks;
        EXIT WHEN batch_deleted = 0;

        INSERT INTO fixed_odds_tick_daily_summary (
            summary_date, race_id, race_entry_id, source, tick_count, price_sum, price_count,
            min_price, max_price, last_price, first_captured_at, last_captured_at
        )
        SELECT DISTINCT ON (summary_date, race_id, race_entry_id, source)
            captured_at::date AS summary_date, race_id, race_entry_id, source,
            COUNT(*) OVER w AS tick_count,
            COALESCE(SUM(price) FILTER (WHERE price IS NOT NULL) OVER w, 0) AS price_sum,
            COUNT(price) OVER w AS price_count,
            MIN(price) OVER w AS min_price,
            MAX(price) OVER w AS max_price,
            FIRST_VALUE(price) OVER w_desc AS last_price,
            MIN(captured_at) OVER w AS first_captured_at,
            MAX(captured_at) OVER w AS last_captured_at
        FROM doomed_fixed_odds_ticks
        WINDOW
            w AS (PARTITION BY captured_at::date, race_id, race_entry_id, source),
            w_desc AS (PARTITION BY captured_at::date, race_id, race_entry_id, source ORDER BY captured_at DESC)
        ORDER BY summary_date, race_id, race_entry_id, source, last_captured_at DESC
        ON CONFLICT (summary_date, race_id, race_entry_id, source) DO UPDATE
        SET tick_count = fixed_odds_tick_daily_summary.tick_count + EXCLUDED.tick_count,
            price_sum = fixed_odds_tick_daily_summary.price_sum + EXCLUDED.price_sum,
            price_count = fixed_odds_tick_daily_summary.price_count + EXCLUDED.price_count,
            min_price = LEAST(fixed_odds_tick_daily_summary.min_price, EXCLUDED.min_price),
            max_price = GREATEST(fixed_odds_tick_daily_summary.max_price, EXCLUDED.max_price),
            last_price = CASE WHEN EXCLUDED.last_captured_at >= fixed_odds_tick_daily_summary.last_captured_at THEN EXCLUDED.last_price ELSE fixed_odds_tick_daily_summary.last_price END,
            first_captured_at = LEAST(fixed_odds_tick_daily_summary.first_captured_at, EXCLUDED.first_captured_at),
            last_captured_at = GREATEST(fixed_odds_tick_daily_summary.last_captured_at, EXCLUDED.last_captured_at),
            updated_at = now();

        DELETE FROM fixed_odds_ticks t USING doomed_fixed_odds_ticks d WHERE t.ctid = d.row_ctid;
        total_deleted := total_deleted + batch_deleted;
        batch_number := batch_number + 1;
        DROP TABLE doomed_fixed_odds_ticks;
        EXIT WHEN batch_deleted < batch_size;
    END LOOP;
    RETURN total_deleted;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp.prune_tote_pools(
    cutoff timestamptz,
    batch_size int,
    max_batches int
) RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    total_deleted bigint := 0;
    batch_deleted bigint := 0;
    batch_number int := 0;
BEGIN
    LOOP
        EXIT WHEN batch_number >= max_batches;
        CREATE TEMP TABLE doomed_tote_pools ON COMMIT DROP AS
        SELECT ctid AS row_ctid, race_id, pool_type, captured_at, pool_size, dividend
        FROM tote_pools
        WHERE captured_at < cutoff
        LIMIT batch_size;
        SELECT COUNT(*) INTO batch_deleted FROM doomed_tote_pools;
        EXIT WHEN batch_deleted = 0;

        INSERT INTO tote_pool_daily_summary (
            summary_date, race_id, pool_type, sample_count, pool_size_sum, pool_size_count,
            max_pool_size, last_pool_size, dividend_sum, dividend_count, first_captured_at, last_captured_at
        )
        SELECT DISTINCT ON (summary_date, race_id, pool_type)
            captured_at::date AS summary_date, race_id, pool_type,
            COUNT(*) OVER w AS sample_count,
            COALESCE(SUM(pool_size) FILTER (WHERE pool_size IS NOT NULL) OVER w, 0) AS pool_size_sum,
            COUNT(pool_size) OVER w AS pool_size_count,
            MAX(pool_size) OVER w AS max_pool_size,
            FIRST_VALUE(pool_size) OVER w_desc AS last_pool_size,
            COALESCE(SUM(dividend) FILTER (WHERE dividend IS NOT NULL) OVER w, 0) AS dividend_sum,
            COUNT(dividend) OVER w AS dividend_count,
            MIN(captured_at) OVER w AS first_captured_at,
            MAX(captured_at) OVER w AS last_captured_at
        FROM doomed_tote_pools
        WINDOW
            w AS (PARTITION BY captured_at::date, race_id, pool_type),
            w_desc AS (PARTITION BY captured_at::date, race_id, pool_type ORDER BY captured_at DESC)
        ORDER BY summary_date, race_id, pool_type, last_captured_at DESC
        ON CONFLICT (summary_date, race_id, pool_type) DO UPDATE
        SET sample_count = tote_pool_daily_summary.sample_count + EXCLUDED.sample_count,
            pool_size_sum = tote_pool_daily_summary.pool_size_sum + EXCLUDED.pool_size_sum,
            pool_size_count = tote_pool_daily_summary.pool_size_count + EXCLUDED.pool_size_count,
            max_pool_size = GREATEST(tote_pool_daily_summary.max_pool_size, EXCLUDED.max_pool_size),
            last_pool_size = CASE WHEN EXCLUDED.last_captured_at >= tote_pool_daily_summary.last_captured_at THEN EXCLUDED.last_pool_size ELSE tote_pool_daily_summary.last_pool_size END,
            dividend_sum = tote_pool_daily_summary.dividend_sum + EXCLUDED.dividend_sum,
            dividend_count = tote_pool_daily_summary.dividend_count + EXCLUDED.dividend_count,
            first_captured_at = LEAST(tote_pool_daily_summary.first_captured_at, EXCLUDED.first_captured_at),
            last_captured_at = GREATEST(tote_pool_daily_summary.last_captured_at, EXCLUDED.last_captured_at),
            updated_at = now();

        DELETE FROM tote_pools t USING doomed_tote_pools d WHERE t.ctid = d.row_ctid;
        total_deleted := total_deleted + batch_deleted;
        batch_number := batch_number + 1;
        DROP TABLE doomed_tote_pools;
        EXIT WHEN batch_deleted < batch_size;
    END LOOP;
    RETURN total_deleted;
END;
$$;

INSERT INTO retention_prune_results(metric, rows_deleted)
VALUES (
    'smart_money_indicators_deleted',
    pg_temp.prune_smart_money(
        current_date - (:smart_money_retention_days::int * interval '1 day'),
        :prune_batch_size::int,
        :prune_max_batches::int
    )
);

INSERT INTO retention_prune_results(metric, rows_deleted)
VALUES (
    'market_signals_deleted',
    pg_temp.prune_market_signals(
        current_date - (:high_frequency_retention_days::int * interval '1 day'),
        :prune_batch_size::int,
        :prune_max_batches::int
    )
);

INSERT INTO retention_prune_results(metric, rows_deleted)
VALUES (
    'tote_pools_deleted',
    pg_temp.prune_tote_pools(
        current_date - (:high_frequency_retention_days::int * interval '1 day'),
        :prune_batch_size::int,
        :prune_max_batches::int
    )
);

INSERT INTO retention_prune_results(metric, rows_deleted)
VALUES (
    'fixed_odds_ticks_deleted',
    pg_temp.prune_fixed_odds_ticks(
        current_date - (:high_frequency_retention_days::int * interval '1 day'),
        :prune_batch_size::int,
        :prune_max_batches::int
    )
);

INSERT INTO retention_prune_results(metric, rows_deleted)
VALUES (
    'odds_snapshots_deleted',
    pg_temp.prune_odds_snapshots(
        current_date - (:high_frequency_retention_days::int * interval '1 day'),
        :prune_batch_size::int,
        :prune_max_batches::int
    )
);

SELECT metric, rows_deleted
FROM retention_prune_results
ORDER BY metric;

VACUUM (ANALYZE) smart_money_indicators;
VACUUM (ANALYZE) market_signals;
VACUUM (ANALYZE) tote_pools;
VACUUM (ANALYZE) fixed_odds_ticks;
VACUUM (ANALYZE) odds_snapshots;

SELECT
    relname AS table,
    n_live_tup AS approx_rows,
    n_dead_tup AS approx_dead,
    pg_size_pretty(pg_total_relation_size(relid)) AS total
FROM pg_stat_user_tables
WHERE relname IN (
    'smart_money_indicators',
    'odds_snapshots',
    'fixed_odds_ticks',
    'market_signals',
    'tote_pools'
)
ORDER BY pg_total_relation_size(relid) DESC;

SELECT pg_advisory_unlock(hashtext('betman_data_retention_prune'));
