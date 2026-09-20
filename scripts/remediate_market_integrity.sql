\set ON_ERROR_STOP on

-- Run only after an external rollback dump has been captured. The poller and
-- scoring writers should be stopped for this bounded transaction.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('betman_market_integrity_remediation'));
SELECT pg_advisory_xact_lock(hashtext('betman_horse_scores_writer'));

CREATE TEMP TABLE invalid_tab_signals ON COMMIT DROP AS
SELECT id, race_id, race_entry_id, detected_at
FROM market_signals
WHERE evidence_json->>'source' = 'tab_money_tracker'
  AND detected_at > created_at + interval '5 minutes';

DELETE FROM smart_money_indicators smi
USING invalid_tab_signals bad
WHERE smi.race_id = bad.race_id
  AND smi.race_entry_id = bad.race_entry_id
  AND smi.indicator_type = 'tab_money_tracker'
  AND smi.detected_at = bad.detected_at;

DELETE FROM market_signals ms
USING invalid_tab_signals bad
WHERE ms.id = bad.id;

DELETE FROM odds_snapshots
WHERE source = 'tab_affiliate_event'
  AND (win_price IS NULL OR win_price <= 0);

UPDATE odds_snapshots
SET place_price = CASE WHEN place_price > 0 THEN place_price END,
    place_sp = CASE WHEN place_sp > 0 THEN place_sp END
WHERE source = 'tab_affiliate_event'
  AND (place_price <= 0 OR place_sp <= 0);

DELETE FROM fixed_odds_ticks
WHERE source IN ('tab_affiliate_event', 'tab_affiliate_fluc')
  AND price <= 0;

-- Rebuild TAB movements and analytics from retained positive observations so
-- failed downstream statements do not leave a partial market history.
DELETE FROM odds_movements
WHERE source = 'tab_affiliate';

WITH ordered AS (
    SELECT
        fot.race_id,
        fot.race_entry_id,
        fot.captured_at,
        fot.time_to_jump_s,
        fot.price,
        LAG(fot.price) OVER (
            PARTITION BY fot.race_entry_id ORDER BY fot.captured_at, fot.id
        ) AS previous_price
    FROM fixed_odds_ticks fot
    WHERE fot.source IN ('tab_affiliate_event', 'tab_affiliate_fluc')
      AND fot.price > 0
), movements AS (
    SELECT *, ((price - previous_price) / previous_price * 100.0)::real AS movement_pct
    FROM ordered
    WHERE previous_price > 0
      AND price > 0
      AND price IS DISTINCT FROM previous_price
)
INSERT INTO odds_movements (
    race_id, race_entry_id, detected_at, time_to_jump_s,
    from_price, to_price, movement_pct, movement_type, source
)
SELECT
    race_id, race_entry_id, captured_at, time_to_jump_s,
    previous_price, price, movement_pct,
    CASE WHEN price < previous_price THEN 'firming' ELSE 'drifting' END,
    'tab_affiliate'
FROM movements
ON CONFLICT DO NOTHING;

CREATE TEMP TABLE tab_market_entries ON COMMIT DROP AS
SELECT DISTINCT race_entry_id
FROM fixed_odds_ticks
WHERE source IN ('tab_affiliate_event', 'tab_affiliate_fluc')
  AND price > 0;

DELETE FROM odds_analytics oa
USING tab_market_entries tab
WHERE oa.race_entry_id = tab.race_entry_id;

WITH stats AS (
    SELECT
        fot.race_id,
        fot.race_entry_id,
        (array_agg(fot.price ORDER BY fot.captured_at, fot.id))[1] AS opening_price,
        (array_agg(fot.price ORDER BY fot.captured_at DESC, fot.id DESC))[1] AS closing_price,
        MIN(fot.price) AS min_price,
        MAX(fot.price) AS max_price,
        COUNT(*)::int AS snapshot_count
    FROM fixed_odds_ticks fot
    WHERE fot.source IN ('tab_affiliate_event', 'tab_affiliate_fluc')
      AND fot.price > 0
    GROUP BY fot.race_id, fot.race_entry_id
), movement_counts AS (
    SELECT
        race_entry_id,
        COUNT(*) FILTER (WHERE movement_type = 'firming')::int AS firmings,
        COUNT(*) FILTER (WHERE movement_type = 'drifting')::int AS driftings,
        MAX(ABS(movement_pct)) AS biggest_move_pct
    FROM odds_movements
    WHERE source = 'tab_affiliate'
    GROUP BY race_entry_id
)
INSERT INTO odds_analytics (
    race_id, race_entry_id, opening_price, closing_price, min_price, max_price,
    price_range, total_movement_pct, firmings_count, driftings_count,
    steam_detected, blowout_detected, biggest_move_pct, biggest_move_type,
    snapshot_count, updated_at
)
SELECT
    s.race_id, s.race_entry_id, s.opening_price, s.closing_price,
    s.min_price, s.max_price, (s.max_price - s.min_price)::real,
    ((s.closing_price - s.opening_price) / s.opening_price * 100.0)::real,
    COALESCE(mc.firmings, 0), COALESCE(mc.driftings, 0),
    s.closing_price <= s.opening_price * 0.8,
    s.closing_price >= s.opening_price * 1.25,
    mc.biggest_move_pct,
    CASE
        WHEN mc.biggest_move_pct IS NULL THEN NULL
        WHEN s.closing_price < s.opening_price THEN 'firming'
        ELSE 'drifting'
    END,
    s.snapshot_count,
    now()
FROM stats s
LEFT JOIN movement_counts mc USING (race_entry_id)
ON CONFLICT (race_entry_id) DO UPDATE SET
    opening_price = EXCLUDED.opening_price,
    closing_price = EXCLUDED.closing_price,
    min_price = EXCLUDED.min_price,
    max_price = EXCLUDED.max_price,
    price_range = EXCLUDED.price_range,
    total_movement_pct = EXCLUDED.total_movement_pct,
    firmings_count = EXCLUDED.firmings_count,
    driftings_count = EXCLUDED.driftings_count,
    steam_detected = EXCLUDED.steam_detected,
    blowout_detected = EXCLUDED.blowout_detected,
    biggest_move_pct = EXCLUDED.biggest_move_pct,
    biggest_move_type = EXCLUDED.biggest_move_type,
    snapshot_count = EXCLUDED.snapshot_count,
    updated_at = EXCLUDED.updated_at;

COMMIT;

ANALYZE odds_snapshots;
ANALYZE fixed_odds_ticks;
ANALYZE odds_movements;
ANALYZE odds_analytics;
ANALYZE market_signals;
