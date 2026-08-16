\set ON_ERROR_STOP on

-- Result integrity is explicit. A race is finished only when every
-- non-scratched entry has one valid, positive finish position.
ALTER TABLE race_results
    ADD COLUMN IF NOT EXISTS result_quality TEXT NOT NULL DEFAULT 'verified';

CREATE TABLE IF NOT EXISTS race_data_quality (
    race_id              INTEGER PRIMARY KEY REFERENCES races (id),
    observed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_status       TEXT NOT NULL,
    source_status        TEXT,
    expected_entries     INTEGER NOT NULL DEFAULT 0,
    valid_result_rows    INTEGER NOT NULL DEFAULT 0,
    invalid_result_rows  INTEGER NOT NULL DEFAULT 0,
    issue_code           TEXT NOT NULL,
    details              JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_race_quality_issue ON race_data_quality (issue_code);

UPDATE race_results
SET result_quality = CASE
    WHEN finish_position IS NULL OR finish_position <= 0 THEN 'invalid_position'
    ELSE 'verified'
END;

-- Keep the denormalised entry result aligned with verified result rows only.
UPDATE race_entries re
SET final_position = rr.finish_position
FROM race_results rr
WHERE rr.race_entry_id = re.id
  AND rr.result_quality = 'verified'
  AND re.final_position IS DISTINCT FROM rr.finish_position;

WITH counts AS (
    SELECT
        r.id AS race_id,
        r.status AS current_status,
        COUNT(re.id) FILTER (WHERE NOT re.scratched) AS expected_entries,
        COUNT(rr.id) FILTER (WHERE rr.result_quality = 'verified') AS valid_result_rows,
        COUNT(rr.id) FILTER (WHERE rr.result_quality <> 'verified') AS invalid_result_rows,
        COUNT(re.id) FILTER (WHERE NOT re.scratched)
          = COUNT(rr.id) FILTER (WHERE rr.result_quality = 'verified')
          AND COUNT(re.id) FILTER (WHERE NOT re.scratched) > 0 AS is_complete
    FROM races r
    LEFT JOIN race_entries re ON re.race_id = r.id
    LEFT JOIN race_results rr ON rr.race_entry_id = re.id
    GROUP BY r.id, r.status
), source_state AS (
    SELECT DISTINCT ON (payload #>> '{data,race,event_id}')
        payload #>> '{data,race,event_id}' AS external_race_id,
        lower(COALESCE(payload #>> '{data,race,status}', '')) AS source_status
    FROM tab_event_payloads
    WHERE payload #>> '{data,race,event_id}' IS NOT NULL
    ORDER BY payload #>> '{data,race,event_id}', fetched_at DESC
), resolved AS (
    SELECT
        c.*,
        COALESCE(ss.source_status, '') AS source_status,
        CASE
            WHEN lower(COALESCE(ss.source_status, '')) = 'abandoned' THEN 'abandoned'
            WHEN c.is_complete THEN 'finished'
            ELSE r.status
        END AS resolved_status
    FROM counts c
    JOIN races r ON r.id = c.race_id
    LEFT JOIN source_state ss ON ss.external_race_id = r.external_race_id
)
UPDATE races r
SET status = resolved.resolved_status
FROM resolved
WHERE r.id = resolved.race_id
  AND r.status IS DISTINCT FROM resolved.resolved_status;

WITH counts AS (
    SELECT
        r.id AS race_id,
        r.status AS current_status,
        COUNT(re.id) FILTER (WHERE NOT re.scratched)::int AS expected_entries,
        COUNT(rr.id) FILTER (WHERE rr.result_quality = 'verified')::int AS valid_result_rows,
        COUNT(rr.id) FILTER (WHERE rr.result_quality <> 'verified')::int AS invalid_result_rows,
        COUNT(re.id) FILTER (WHERE NOT re.scratched)
          = COUNT(rr.id) FILTER (WHERE rr.result_quality = 'verified')
          AND COUNT(re.id) FILTER (WHERE NOT re.scratched) > 0 AS is_complete
    FROM races r
    LEFT JOIN race_entries re ON re.race_id = r.id
    LEFT JOIN race_results rr ON rr.race_entry_id = re.id
    GROUP BY r.id, r.status
)
INSERT INTO race_data_quality (
    race_id, observed_at, current_status, expected_entries,
    valid_result_rows, invalid_result_rows, issue_code, details
)
SELECT
    race_id,
    now(),
    current_status,
    expected_entries,
    valid_result_rows,
    invalid_result_rows,
    CASE
        WHEN invalid_result_rows > 0 THEN 'invalid_result_rows'
        WHEN current_status = 'finished' AND NOT is_complete THEN 'partial_results'
        WHEN current_status = 'scheduled'
             AND COALESCE((SELECT COALESCE(actual_start_time, scheduled_start_time) < now()
                           FROM races r2 WHERE r2.id = counts.race_id), false)
             AND NOT is_complete THEN 'stale_scheduled_no_complete_result'
        ELSE 'ok'
    END,
    jsonb_build_object('complete_result_set', is_complete)
FROM counts
ON CONFLICT (race_id) DO UPDATE SET
    observed_at = EXCLUDED.observed_at,
    current_status = EXCLUDED.current_status,
    expected_entries = EXCLUDED.expected_entries,
    valid_result_rows = EXCLUDED.valid_result_rows,
    invalid_result_rows = EXCLUDED.invalid_result_rows,
    issue_code = EXCLUDED.issue_code,
    details = EXCLUDED.details;

ANALYZE races;
ANALYZE race_entries;
ANALYZE race_results;
ANALYZE race_data_quality;

INSERT INTO schema_migrations (version) VALUES ('009_result_integrity.sql')
ON CONFLICT (version) DO NOTHING;
