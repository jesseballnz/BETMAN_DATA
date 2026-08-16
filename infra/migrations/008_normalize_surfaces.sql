\set ON_ERROR_STOP on

-- Normalize the source feed's surface values before downstream analytics use them.
-- TAB commonly omits track_surface; Synthetic conditions and track names remain
-- authoritative indicators. All remaining race meetings are turf in this feed.

WITH meeting_surface AS (
    SELECT DISTINCT ON (payload #>> '{data,race,meeting_id}')
        payload #>> '{data,race,meeting_id}' AS external_meeting_id,
        CASE
            WHEN lower(COALESCE(payload #>> '{data,race,track_surface}', '')) ~ 'synthetic|poly|tapeta|awt'
              OR lower(COALESCE(payload #>> '{data,race,track_condition}', '')) ~ 'synthetic|poly|tapeta|awt'
              OR lower(COALESCE(payload #>> '{data,race,display_meeting_name}', payload #>> '{data,race,meeting_name}', '')) ~ 'synthetic|poly|tapeta|awt'
                THEN 'synthetic'
            ELSE 'turf'
        END AS surface
    FROM tab_event_payloads
    WHERE payload #>> '{data,race,meeting_id}' IS NOT NULL
    ORDER BY payload #>> '{data,race,meeting_id}', fetched_at DESC
)
UPDATE meetings m
SET surface = ms.surface
FROM meeting_surface ms
WHERE m.external_meeting_id = ms.external_meeting_id;

WITH race_surface AS (
    SELECT DISTINCT ON (payload #>> '{data,race,event_id}')
        payload #>> '{data,race,event_id}' AS external_race_id,
        CASE
            WHEN lower(COALESCE(payload #>> '{data,race,track_surface}', '')) ~ 'synthetic|poly|tapeta|awt'
              OR lower(COALESCE(payload #>> '{data,race,track_condition}', '')) ~ 'synthetic|poly|tapeta|awt'
              OR lower(COALESCE(payload #>> '{data,race,display_meeting_name}', payload #>> '{data,race,meeting_name}', '')) ~ 'synthetic|poly|tapeta|awt'
                THEN 'synthetic'
            ELSE 'turf'
        END AS surface
    FROM tab_event_payloads
    WHERE payload #>> '{data,race,event_id}' IS NOT NULL
    ORDER BY payload #>> '{data,race,event_id}', fetched_at DESC
)
UPDATE races r
SET surface = rs.surface
FROM race_surface rs
WHERE r.external_race_id = rs.external_race_id;

UPDATE barrier_outcomes bo
SET surface = r.surface
FROM races r
WHERE r.id = bo.race_id;

ANALYZE meetings;
ANALYZE races;
ANALYZE barrier_outcomes;
ANALYZE barrier_statistics;

INSERT INTO schema_migrations (version) VALUES ('008_normalize_surfaces.sql')
ON CONFLICT (version) DO NOTHING;
