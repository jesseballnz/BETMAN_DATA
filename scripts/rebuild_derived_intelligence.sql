\set ON_ERROR_STOP on

-- Rebuild deterministic historical aggregates from verified race results.
-- No estimate is inserted when the source field is absent.
BEGIN;

TRUNCATE trainer_stats, jockey_stats, trainer_patterns, track_heatmap_cells;

WITH result_base AS (
    SELECT
        re.trainer,
        re.jockey_or_driver AS jockey,
        re.barrier_number,
        re.run_number_this_prep AS run_number,
        m.track_name,
        COALESCE(r.surface, m.surface, 'unknown') AS surface,
        COALESCE(tc.condition_category, 'unknown') AS condition_category,
        CASE WHEN r.distance_m IS NULL THEN 'unknown'
             WHEN r.distance_m <= 1200 THEN 'sprint'
             WHEN r.distance_m <= 1600 THEN 'mile'
             ELSE 'staying' END AS distance_band,
        r.race_class_group,
        rr.finish_position,
        rr.finish_position = 1 AS won,
        rr.finish_position <= 3 AS placed
    FROM races r
    JOIN meetings m ON m.id = r.meeting_id
    JOIN race_entries re ON re.race_id = r.id AND NOT re.scratched
    JOIN race_results rr ON rr.race_entry_id = re.id
        AND COALESCE(rr.result_quality, 'verified') = 'verified'
    LEFT JOIN LATERAL (
        SELECT condition_category
        FROM track_condition_readings tcr
        WHERE tcr.race_id = r.id OR (tcr.race_id IS NULL AND tcr.meeting_id = r.meeting_id)
        ORDER BY (tcr.race_id = r.id) DESC, tcr.recorded_at DESC
        LIMIT 1
    ) tc ON true
    WHERE r.status = 'finished'
)
INSERT INTO trainer_stats (
    trainer, track_name, surface, condition_category, distance_band,
    race_class_group, run_number, runners, wins, places, win_rate, updated_at
)
SELECT trainer, track_name, surface, condition_category, distance_band,
       race_class_group, run_number, count(*)::int,
       count(*) FILTER (WHERE won)::int,
       count(*) FILTER (WHERE placed)::int,
       (100.0 * count(*) FILTER (WHERE won) / NULLIF(count(*), 0))::real,
       now()
FROM result_base
WHERE NULLIF(trim(trainer), '') IS NOT NULL
GROUP BY trainer, track_name, surface, condition_category, distance_band,
         race_class_group, run_number;

WITH result_base AS (
    SELECT
        re.jockey_or_driver AS jockey,
        re.barrier_number,
        m.track_name,
        rr.finish_position,
        rr.finish_position = 1 AS won,
        COALESCE(tc.condition_category, 'unknown') AS condition_category
    FROM races r
    JOIN meetings m ON m.id = r.meeting_id
    JOIN race_entries re ON re.race_id = r.id AND NOT re.scratched
    JOIN race_results rr ON rr.race_entry_id = re.id
        AND COALESCE(rr.result_quality, 'verified') = 'verified'
    LEFT JOIN LATERAL (
        SELECT condition_category
        FROM track_condition_readings tcr
        WHERE tcr.race_id = r.id OR (tcr.race_id IS NULL AND tcr.meeting_id = r.meeting_id)
        ORDER BY (tcr.race_id = r.id) DESC, tcr.recorded_at DESC
        LIMIT 1
    ) tc ON true
    WHERE r.status = 'finished'
)
INSERT INTO jockey_stats (
    jockey, track_name, gate_zone, going, race_style,
    runners, wins, win_rate, updated_at
)
SELECT jockey,
       track_name,
       CASE WHEN barrier_number <= 3 THEN 'inside_third'
            WHEN barrier_number <= 6 THEN 'middle_third'
            ELSE 'outside_third' END,
       CASE WHEN condition_category IN ('heavy', 'soft') THEN 'wet'
            WHEN condition_category IN ('good', 'firm') THEN 'dry'
            ELSE 'all' END,
       NULL,
       count(*)::int,
       count(*) FILTER (WHERE won)::int,
       (100.0 * count(*) FILTER (WHERE won) / NULLIF(count(*), 0))::real,
       now()
FROM result_base
WHERE NULLIF(trim(jockey), '') IS NOT NULL
  AND barrier_number IS NOT NULL
GROUP BY jockey, track_name,
         CASE WHEN barrier_number <= 3 THEN 'inside_third'
              WHEN barrier_number <= 6 THEN 'middle_third'
              ELSE 'outside_third' END,
         CASE WHEN condition_category IN ('heavy', 'soft') THEN 'wet'
              WHEN condition_category IN ('good', 'firm') THEN 'dry'
              ELSE 'all' END;

INSERT INTO trainer_patterns (trainer, pattern_type, runners, wins, win_rate, updated_at)
SELECT trainer, 'first_up', count(*)::int,
       count(*) FILTER (WHERE finish_position = 1)::int,
       (100.0 * count(*) FILTER (WHERE finish_position = 1) / NULLIF(count(*), 0))::real,
       now()
FROM (
    SELECT re.trainer, re.run_number_this_prep, rr.finish_position
    FROM race_entries re
    JOIN race_results rr ON rr.race_entry_id = re.id
       AND COALESCE(rr.result_quality, 'verified') = 'verified'
    JOIN races r ON r.id = re.race_id AND r.status = 'finished'
    WHERE re.run_number_this_prep = 1
) x
WHERE NULLIF(trim(trainer), '') IS NOT NULL
GROUP BY trainer;

INSERT INTO track_heatmap_cells (
    track_name, surface, condition_category, distance_band, zone,
    distance_from_finish_band, win_count, place_count, runner_count,
    win_rate, place_rate, intensity, updated_at
)
SELECT track_name,
       COALESCE(surface, 'unknown'),
       COALESCE(condition_category, 'unknown'),
       CASE WHEN distance_m IS NULL THEN 'unknown'
            WHEN distance_m <= 1200 THEN 'sprint'
            WHEN distance_m <= 1600 THEN 'mile'
            ELSE 'staying' END,
       CASE relative_barrier WHEN 'inside_third' THEN 'inside'
            WHEN 'middle_third' THEN 'middle'
            WHEN 'outside_third' THEN 'outside' ELSE 'unknown' END,
       'all',
       count(*) FILTER (WHERE won)::int,
       count(*) FILTER (WHERE placed)::int,
       count(*)::int,
       (100.0 * count(*) FILTER (WHERE won) / NULLIF(count(*), 0))::real,
       (100.0 * count(*) FILTER (WHERE placed) / NULLIF(count(*), 0))::real,
       (count(*) FILTER (WHERE won)::real / NULLIF(count(*), 0)),
       now()
FROM barrier_outcomes
WHERE final_position > 0
GROUP BY track_name, surface, condition_category,
         CASE WHEN distance_m IS NULL THEN 'unknown'
              WHEN distance_m <= 1200 THEN 'sprint'
              WHEN distance_m <= 1600 THEN 'mile'
              ELSE 'staying' END,
         CASE relative_barrier WHEN 'inside_third' THEN 'inside'
              WHEN 'middle_third' THEN 'middle'
              WHEN 'outside_third' THEN 'outside' ELSE 'unknown' END;

COMMIT;
