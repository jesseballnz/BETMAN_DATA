\set ON_ERROR_STOP on

-- Materialise resulted race entries into the barrier outcome ledger.
-- The TAB loader populates race_entries.final_position; this table is the
-- denormalised analytics ledger used by track/barrier endpoints.

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ux_barrier_outcomes_race_entry
    ON barrier_outcomes (race_entry_id);

WITH eligible_entries AS (
    SELECT
        re.id AS race_entry_id,
        re.race_id,
        re.runner_id,
        re.barrier_number,
        re.final_position,
        r.distance_m,
        r.race_class_code,
        r.race_class_group,
        COALESCE(NULLIF(r.surface, ''), NULLIF(m.surface, ''), 'unknown') AS surface,
        m.track_name,
        m.meeting_date AS race_date,
        COUNT(*) OVER (PARTITION BY re.race_id) AS field_size
    FROM race_entries re
    JOIN races r ON r.id = re.race_id
    JOIN meetings m ON m.id = r.meeting_id
    WHERE re.scratched = false
      AND re.barrier_number IS NOT NULL
      AND re.final_position IS NOT NULL
      AND r.distance_m IS NOT NULL
      AND m.track_name IS NOT NULL
      AND m.meeting_date IS NOT NULL
), enriched AS (
    SELECT
        ee.*,
        rr.margin_lengths,
        tc.condition_code,
        tc.condition_category,
        tc.penetrometer_value,
        tc.avg_soil_moisture_pct
    FROM eligible_entries ee
    LEFT JOIN race_results rr ON rr.race_entry_id = ee.race_entry_id
    LEFT JOIN LATERAL (
        SELECT
            tcr.condition_code,
            tcr.condition_category,
            tcr.penetrometer_value,
            tcr.avg_soil_moisture_pct
        FROM track_condition_readings tcr
        WHERE tcr.race_id = ee.race_id
           OR (tcr.race_id IS NULL AND tcr.meeting_id = (
                SELECT r.meeting_id FROM races r WHERE r.id = ee.race_id
           ))
        ORDER BY CASE WHEN tcr.race_id = ee.race_id THEN 0 ELSE 1 END,
                 tcr.recorded_at DESC
        LIMIT 1
    ) tc ON true
)
INSERT INTO barrier_outcomes (
    race_id,
    race_entry_id,
    runner_id,
    barrier_number,
    field_size,
    relative_barrier,
    final_position,
    won,
    placed,
    unplaced,
    margin_lengths,
    track_name,
    surface,
    distance_m,
    race_class_code,
    race_class_group,
    condition_code,
    condition_category,
    penetrometer_value,
    avg_soil_moisture_pct,
    race_date
)
SELECT
    race_id,
    race_entry_id,
    runner_id,
    barrier_number,
    field_size,
    CASE
        WHEN barrier_number <= CEIL(field_size::numeric / 3.0) THEN 'inside_third'
        WHEN barrier_number <= CEIL(field_size::numeric * 2.0 / 3.0) THEN 'middle_third'
        ELSE 'outside_third'
    END,
    final_position,
    final_position = 1,
    final_position <= 3,
    final_position > 3,
    margin_lengths,
    track_name,
    surface,
    distance_m,
    race_class_code,
    race_class_group,
    condition_code,
    condition_category,
    penetrometer_value,
    avg_soil_moisture_pct,
    race_date
FROM enriched
ON CONFLICT (race_entry_id) DO UPDATE
SET barrier_number = EXCLUDED.barrier_number,
    field_size = EXCLUDED.field_size,
    relative_barrier = EXCLUDED.relative_barrier,
    final_position = EXCLUDED.final_position,
    won = EXCLUDED.won,
    placed = EXCLUDED.placed,
    unplaced = EXCLUDED.unplaced,
    margin_lengths = EXCLUDED.margin_lengths,
    track_name = EXCLUDED.track_name,
    surface = EXCLUDED.surface,
    distance_m = EXCLUDED.distance_m,
    race_class_code = EXCLUDED.race_class_code,
    race_class_group = EXCLUDED.race_class_group,
    condition_code = EXCLUDED.condition_code,
    condition_category = EXCLUDED.condition_category,
    penetrometer_value = EXCLUDED.penetrometer_value,
    avg_soil_moisture_pct = EXCLUDED.avg_soil_moisture_pct,
    race_date = EXCLUDED.race_date;

ANALYZE barrier_outcomes;

INSERT INTO schema_migrations (version) VALUES ('007_backfill_barrier_outcomes.sql')
ON CONFLICT (version) DO NOTHING;
