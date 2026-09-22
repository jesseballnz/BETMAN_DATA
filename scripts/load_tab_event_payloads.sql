\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS tab_event_payloads (
    source TEXT NOT NULL,
    external_race_id TEXT PRIMARY KEY,
    country TEXT,
    race_date DATE,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_meetings_external_meeting_id
    ON meetings (external_meeting_id)
    WHERE external_meeting_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_races_external_race_id
    ON races (external_race_id)
    WHERE external_race_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_runners_external_runner_id
    ON runners (external_runner_id)
    WHERE external_runner_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_race_entries_race_runner
    ON race_entries (race_id, runner_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_smart_money_signal_natural
    ON smart_money_indicators (race_id, race_entry_id, indicator_type, detected_at);

CREATE TEMP TABLE tab_event_import_raw (line TEXT);
\copy tab_event_import_raw(line) FROM '__TAB_EVENT_JSONL__' WITH (FORMAT csv, DELIMITER E'\x03', QUOTE E'\x01', ESCAPE E'\x02')

CREATE TEMP TABLE tab_event_import_parsed AS
SELECT line::jsonb AS payload
FROM tab_event_import_raw
WHERE NULLIF(line, '') IS NOT NULL;

CREATE TEMP TABLE tab_event_status_overrides AS
SELECT DISTINCT ON (payload #>> '{data,race,event_id}')
    payload #>> '{data,race,event_id}' AS external_race_id,
    payload->>'_betman_listing_race_status' AS listing_status
FROM tab_event_import_parsed
WHERE payload #>> '{data,race,event_id}' IS NOT NULL
  AND NULLIF(payload->>'_betman_listing_race_status', '') IS NOT NULL
ORDER BY payload #>> '{data,race,event_id}';
CREATE UNIQUE INDEX ON tab_event_status_overrides (external_race_id);

INSERT INTO tab_event_payloads (source, external_race_id, country, race_date, fetched_at, payload)
SELECT
    'tab_affiliate',
    payload #>> '{data,race,event_id}',
    payload #>> '{data,race,country}',
    NULLIF(payload #>> '{data,race,race_date_nz}', '')::date,
    COALESCE(NULLIF(payload->>'_betman_fetched_at', '')::timestamptz, now()),
    payload
FROM tab_event_import_parsed src
WHERE payload #>> '{data,race,event_id}' IS NOT NULL
  AND payload #>> '{data,race,type}' = 'T'
  AND COALESCE((payload->>'_betman_status_only')::boolean, false) = false
ON CONFLICT (external_race_id) DO UPDATE
SET country = EXCLUDED.country,
    race_date = EXCLUDED.race_date,
    payload = EXCLUDED.payload,
    fetched_at = EXCLUDED.fetched_at;

-- Every materialisation below is scoped to this poll's payloads. Previously
-- the loader replayed the entire retained payload history on every cycle,
-- multiplying identical odds/tote rows and repeatedly locking horse_scores.
CREATE TEMP TABLE tab_event_import_ids AS
SELECT DISTINCT line::jsonb #>> '{data,race,event_id}' AS external_race_id
FROM tab_event_import_raw
WHERE NULLIF(line, '') IS NOT NULL
  AND line::jsonb #>> '{data,race,event_id}' IS NOT NULL;
CREATE UNIQUE INDEX ON tab_event_import_ids (external_race_id);
CREATE TEMP TABLE tab_event_payloads_current AS
SELECT
    tep.source,
    tep.external_race_id,
    tep.country,
    tep.race_date,
    tep.fetched_at,
    tep.payload || CASE WHEN o.listing_status IS NOT NULL
        THEN jsonb_build_object('_betman_listing_race_status', o.listing_status)
        ELSE '{}'::jsonb END AS payload
FROM tab_event_payloads tep
JOIN tab_event_import_ids imported USING (external_race_id)
LEFT JOIN tab_event_status_overrides o USING (external_race_id);
CREATE UNIQUE INDEX ON tab_event_payloads_current (external_race_id);

DELETE FROM tab_event_payloads
WHERE payload #>> '{data,race,type}' IS DISTINCT FROM 'T';

INSERT INTO race_classes (code, "group", rank, description)
SELECT DISTINCT ON (code) code, "group", rank, description
FROM (
    SELECT
        COALESCE(NULLIF(payload #>> '{data,race,class}', ''), 'UNKNOWN') AS code,
        CASE
            WHEN payload #>> '{data,race,group}' ILIKE 'G1%' THEN 'group'
            WHEN payload #>> '{data,race,group}' ILIKE 'G2%' THEN 'group'
            WHEN payload #>> '{data,race,group}' ILIKE 'G3%' THEN 'group'
            WHEN payload #>> '{data,race,class}' ILIKE '%MDN%' THEN 'maiden'
            WHEN payload #>> '{data,race,class}' ILIKE '%RATING%' THEN 'rating_band'
            WHEN payload #>> '{data,race,class}' ILIKE '%BM%' THEN 'benchmark'
            ELSE 'open'
        END AS "group",
        CASE
            WHEN payload #>> '{data,race,group}' ILIKE 'G1%' THEN 1
            WHEN payload #>> '{data,race,group}' ILIKE 'G2%' THEN 2
            WHEN payload #>> '{data,race,group}' ILIKE 'G3%' THEN 3
            WHEN payload #>> '{data,race,class}' ILIKE '%MDN%' THEN 80
            ELSE 50
        END AS rank,
        NULLIF(payload #>> '{data,race,description}', '') AS description
    FROM tab_event_payloads_current
    WHERE payload #>> '{data,race,event_id}' IS NOT NULL
) classes
ORDER BY code, description NULLS LAST
ON CONFLICT (code) DO UPDATE
SET "group" = EXCLUDED."group",
    rank = EXCLUDED.rank,
    description = COALESCE(EXCLUDED.description, race_classes.description);

WITH race_src AS (
    SELECT (payload #> '{data,race}') ||
        CASE WHEN NULLIF(payload->>'_betman_listing_race_status', '') IS NOT NULL
            THEN jsonb_build_object('status', payload->>'_betman_listing_race_status')
            ELSE '{}'::jsonb END AS race
    FROM tab_event_payloads_current
)
INSERT INTO meetings (external_meeting_id, track_name, meeting_date, surface, jurisdiction, status)
SELECT DISTINCT ON (race->>'meeting_id')
    race->>'meeting_id',
    COALESCE(NULLIF(race->>'display_meeting_name', ''), race->>'meeting_name'),
    (race->>'race_date_nz')::date,
    CASE
        WHEN lower(COALESCE(NULLIF(race->>'track_surface', ''), '')) ~ 'synthetic|poly|tapeta|awt'
          OR lower(COALESCE(NULLIF(race->>'track_condition', ''), '')) ~ 'synthetic|poly|tapeta|awt'
          OR lower(COALESCE(NULLIF(race->>'display_meeting_name', ''), NULLIF(race->>'meeting_name', ''), '')) ~ 'synthetic|poly|tapeta|awt'
            THEN 'synthetic'
        ELSE 'turf'
    END,
    NULLIF(race->>'country', ''),
    CASE
        WHEN lower(COALESCE(race->>'status', '')) IN ('final', 'closed') THEN 'completed'
        WHEN lower(COALESCE(race->>'status', '')) IN ('abandoned') THEN 'abandoned'
        ELSE 'scheduled'
    END
FROM race_src
WHERE race->>'meeting_id' IS NOT NULL
ORDER BY race->>'meeting_id', race->>'race_date_nz' DESC
ON CONFLICT (external_meeting_id) WHERE external_meeting_id IS NOT NULL DO UPDATE
SET track_name = EXCLUDED.track_name,
    meeting_date = EXCLUDED.meeting_date,
    surface = EXCLUDED.surface,
    jurisdiction = EXCLUDED.jurisdiction,
    status = CASE
        WHEN meetings.status IN ('completed', 'abandoned') AND EXCLUDED.status = 'scheduled'
            THEN meetings.status
        ELSE EXCLUDED.status
    END;

WITH race_src AS (
    SELECT (payload #> '{data,race}') ||
        CASE WHEN NULLIF(payload->>'_betman_listing_race_status', '') IS NOT NULL
            THEN jsonb_build_object('status', payload->>'_betman_listing_race_status')
            ELSE '{}'::jsonb END AS race
    FROM tab_event_payloads_current
)
INSERT INTO races (
    meeting_id,
    external_race_id,
    race_number,
    name,
    distance_m,
    scheduled_start_time,
    actual_start_time,
    race_class_id,
    race_class_code,
    race_class_group,
    prize_money,
    surface,
    status,
    stake,
    track_direction,
    rail_position,
    conditions_description
)
SELECT
    m.id,
    race->>'event_id',
    NULLIF(race->>'race_number', '')::int,
    NULLIF(race->>'description', ''),
    NULLIF(race->>'distance', '')::int,
    CASE WHEN NULLIF(race->>'advertised_start', '') IS NULL THEN NULL ELSE to_timestamp((race->>'advertised_start')::double precision) END,
    CASE WHEN NULLIF(race->>'actual_start', '') IS NULL OR race->>'actual_start' = '0' THEN NULL ELSE to_timestamp((race->>'actual_start')::double precision) END,
    rc.id,
    COALESCE(NULLIF(race->>'class', ''), 'UNKNOWN'),
    rc."group",
    NULLIF(race #>> '{prize_monies,total_value}', '')::numeric,
    CASE
        WHEN lower(COALESCE(NULLIF(race->>'track_surface', ''), '')) ~ 'synthetic|poly|tapeta|awt'
          OR lower(COALESCE(NULLIF(race->>'track_condition', ''), '')) ~ 'synthetic|poly|tapeta|awt'
          OR lower(COALESCE(NULLIF(race->>'display_meeting_name', ''), NULLIF(race->>'meeting_name', ''), '')) ~ 'synthetic|poly|tapeta|awt'
            THEN 'synthetic'
        ELSE 'turf'
    END,
    CASE
        WHEN lower(COALESCE(race->>'status', '')) IN ('final', 'closed') THEN 'finished'
        WHEN lower(COALESCE(race->>'status', '')) IN ('abandoned') THEN 'abandoned'
        ELSE 'scheduled'
    END,
    NULLIF(race #>> '{prize_monies,total_value}', '')::numeric,
    NULLIF(race->>'track_direction', ''),
    NULLIF(race->>'rail_position', ''),
    NULLIF(concat_ws('; ', NULLIF(race->>'track_condition', ''), NULLIF(race->>'weather', ''), NULLIF(race->>'comment', '')), '')
FROM race_src
JOIN meetings m ON m.external_meeting_id = race->>'meeting_id'
LEFT JOIN race_classes rc ON rc.code = COALESCE(NULLIF(race->>'class', ''), 'UNKNOWN')
WHERE race->>'event_id' IS NOT NULL
ON CONFLICT (external_race_id) WHERE external_race_id IS NOT NULL DO UPDATE
SET meeting_id = EXCLUDED.meeting_id,
    race_number = EXCLUDED.race_number,
    name = EXCLUDED.name,
    distance_m = EXCLUDED.distance_m,
    scheduled_start_time = EXCLUDED.scheduled_start_time,
    actual_start_time = EXCLUDED.actual_start_time,
    race_class_id = EXCLUDED.race_class_id,
    race_class_code = EXCLUDED.race_class_code,
    race_class_group = EXCLUDED.race_class_group,
    prize_money = EXCLUDED.prize_money,
    surface = EXCLUDED.surface,
    status = CASE
        WHEN races.status IN ('finished', 'abandoned') AND EXCLUDED.status = 'scheduled'
            THEN races.status
        ELSE EXCLUDED.status
    END,
    stake = EXCLUDED.stake,
    track_direction = EXCLUDED.track_direction,
    rail_position = EXCLUDED.rail_position,
    conditions_description = EXCLUDED.conditions_description;

WITH runner_src AS (
    SELECT DISTINCT ON (runner->>'entrant_id')
        runner
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,runners}') = 'array' THEN tep.payload #> '{data,runners}' ELSE '[]'::jsonb END) AS runner
    WHERE runner->>'entrant_id' IS NOT NULL
    ORDER BY runner->>'entrant_id'
)
INSERT INTO runners (external_runner_id, external_horse_id, name, type, country_of_origin)
SELECT
    runner->>'entrant_id',
    NULLIF(runner->>'horse_id', ''),
    runner->>'name',
    'thoroughbred',
    NULLIF(runner->>'country', '')
FROM runner_src
WHERE runner->>'name' IS NOT NULL
ON CONFLICT (external_runner_id) WHERE external_runner_id IS NOT NULL DO UPDATE
SET external_horse_id = COALESCE(EXCLUDED.external_horse_id, runners.external_horse_id),
    name = EXCLUDED.name,
    type = EXCLUDED.type,
    country_of_origin = EXCLUDED.country_of_origin;

WITH runner_src AS (
    SELECT DISTINCT ON (runner->>'entrant_id')
        runner
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,runners}') = 'array' THEN tep.payload #> '{data,runners}' ELSE '[]'::jsonb END) AS runner
    WHERE runner->>'entrant_id' IS NOT NULL
    ORDER BY runner->>'entrant_id'
)
INSERT INTO pedigrees (runner_id, sire, dam, damsire, colour, provider_name, updated_at)
SELECT
    run.id,
    NULLIF(runner_src.runner->>'sire', ''),
    NULLIF(runner_src.runner->>'dam', ''),
    NULLIF(runner_src.runner->>'dam_sire', ''),
    NULLIF(runner_src.runner->>'colour', ''),
    'tab_affiliate',
    now()
FROM runner_src
JOIN runners run ON run.external_runner_id = runner_src.runner->>'entrant_id'
WHERE NULLIF(runner_src.runner->>'sire', '') IS NOT NULL
   OR NULLIF(runner_src.runner->>'dam', '') IS NOT NULL
   OR NULLIF(runner_src.runner->>'dam_sire', '') IS NOT NULL
ON CONFLICT (runner_id) DO UPDATE
SET sire = COALESCE(EXCLUDED.sire, pedigrees.sire),
    dam = COALESCE(EXCLUDED.dam, pedigrees.dam),
    damsire = COALESCE(EXCLUDED.damsire, pedigrees.damsire),
    colour = COALESCE(EXCLUDED.colour, pedigrees.colour),
    provider_name = EXCLUDED.provider_name,
    updated_at = EXCLUDED.updated_at;

WITH entry_src AS (
    SELECT
        race->>'event_id' AS external_race_id,
        runner
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL (SELECT tep.payload #> '{data,race}' AS race) race_doc
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,runners}') = 'array' THEN tep.payload #> '{data,runners}' ELSE '[]'::jsonb END) AS runner
    WHERE runner->>'entrant_id' IS NOT NULL
)
INSERT INTO race_entries (
    race_id,
    runner_id,
    barrier_number,
    saddle_cloth,
    jockey_or_driver,
    trainer,
    weight_kg,
    scratched,
    final_position,
    age,
    sex,
    career_starts,
    career_wins,
    gear_changes_json
)
SELECT
    r.id,
    run.id,
    NULLIF(entry_src.runner->>'barrier', '')::int,
    NULLIF(entry_src.runner->>'runner_number', ''),
    NULLIF(entry_src.runner->>'jockey', ''),
    NULLIF(entry_src.runner->>'trainer_name', ''),
    NULLIF(entry_src.runner #>> '{weight,total}', '')::numeric,
    COALESCE(NULLIF(entry_src.runner->>'is_scratched', '')::boolean, false),
    result.finish_position,
    NULLIF(entry_src.runner->>'age', '')::int,
    NULLIF(entry_src.runner->>'sex', ''),
    NULLIF(entry_src.runner #>> '{past_performances,overall,number_of_starts}', '')::int,
    NULLIF(entry_src.runner #>> '{past_performances,overall,number_of_wins}', '')::int,
    jsonb_build_object('gear', NULLIF(entry_src.runner->>'gear', ''), 'form_indicators', COALESCE(entry_src.runner->'form_indicators', '[]'::jsonb))
FROM entry_src
JOIN races r ON r.external_race_id = entry_src.external_race_id
JOIN runners run ON run.external_runner_id = entry_src.runner->>'entrant_id'
LEFT JOIN LATERAL (
    SELECT NULLIF(res->>'position', '')::int AS finish_position
    FROM tab_event_payloads_current tep2
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep2.payload #> '{data,results}') = 'array' THEN tep2.payload #> '{data,results}' ELSE '[]'::jsonb END) AS res
    WHERE tep2.external_race_id = entry_src.external_race_id
      AND res->>'entrant_id' = entry_src.runner->>'entrant_id'
    LIMIT 1
) result ON true
ON CONFLICT (race_id, runner_id) DO UPDATE
SET barrier_number = EXCLUDED.barrier_number,
    saddle_cloth = EXCLUDED.saddle_cloth,
    jockey_or_driver = EXCLUDED.jockey_or_driver,
    trainer = EXCLUDED.trainer,
    weight_kg = EXCLUDED.weight_kg,
    scratched = EXCLUDED.scratched,
    final_position = EXCLUDED.final_position,
    age = EXCLUDED.age,
    sex = EXCLUDED.sex,
    career_starts = EXCLUDED.career_starts,
    career_wins = EXCLUDED.career_wins,
    gear_changes_json = EXCLUDED.gear_changes_json;

WITH result_src AS (
    SELECT
        tep.external_race_id,
        res
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,results}') = 'array' THEN tep.payload #> '{data,results}' ELSE '[]'::jsonb END) AS res
)
INSERT INTO race_results (race_id, race_entry_id, finish_position, margin_lengths, finish_time_s)
SELECT
    r.id,
    re.id,
    NULLIF(result_src.res->>'position', '')::int,
    NULLIF(result_src.res->>'margin_length', '')::real,
    COALESCE(NULLIF(result_src.res->>'time_ran', '')::real, NULLIF(result_src.res->>'winning_time', '')::real)
FROM result_src
JOIN races r ON r.external_race_id = result_src.external_race_id
JOIN runners run ON run.external_runner_id = result_src.res->>'entrant_id'
JOIN race_entries re ON re.race_id = r.id AND re.runner_id = run.id
WHERE NULLIF(result_src.res->>'position', '') IS NOT NULL
ON CONFLICT (race_entry_id) DO UPDATE
SET finish_position = EXCLUDED.finish_position,
    margin_lengths = EXCLUDED.margin_lengths,
    finish_time_s = EXCLUDED.finish_time_s;

-- Official result rows are authoritative for finishing position. Some runner
-- objects omit their position even though the matching result row is complete.
UPDATE race_entries re
SET final_position = rr.finish_position
FROM race_results rr
JOIN races r ON r.id = rr.race_id
JOIN tab_event_import_ids imported ON imported.external_race_id = r.external_race_id
WHERE rr.race_entry_id = re.id
  AND rr.finish_position > 0
  AND re.final_position IS DISTINCT FROM rr.finish_position;

WITH source_rows AS (
    SELECT
        r.id AS race_id,
        r.meeting_id,
        tep.fetched_at,
        NULLIF(trim(tep.payload #>> '{data,race,track_condition}'), '') AS condition_code,
        NULLIF(trim(tep.payload #>> '{data,race,weather}'), '') AS weather
    FROM tab_event_payloads_current tep
    JOIN races r ON r.external_race_id = tep.external_race_id
)
INSERT INTO track_condition_readings (
    meeting_id, race_id, condition_code, condition_category, recorded_at, source, notes
)
SELECT
    meeting_id,
    race_id,
    condition_code,
    CASE
        WHEN lower(condition_code) ~ 'heavy' THEN 'heavy'
        WHEN lower(condition_code) ~ 'soft|slow' THEN 'soft'
        WHEN lower(condition_code) ~ 'good' THEN 'good'
        WHEN lower(condition_code) ~ 'firm|fast' THEN 'firm'
        WHEN lower(condition_code) ~ 'synthetic|poly|tapeta|awt' THEN 'synthetic'
        ELSE 'unknown'
    END,
    fetched_at,
    'tab_affiliate',
    CASE WHEN weather IS NULL THEN NULL ELSE 'Official race weather: ' || weather END
FROM source_rows
WHERE condition_code IS NOT NULL
ON CONFLICT (meeting_id, (COALESCE(race_id, 0)), condition_code, source)
    WHERE source = 'tab_affiliate'
DO UPDATE SET
    condition_category = EXCLUDED.condition_category,
    recorded_at = EXCLUDED.recorded_at,
    notes = EXCLUDED.notes;

WITH counts AS (
    SELECT
        r.id AS race_id,
        r.status AS current_status,
        lower(COALESCE(tep.payload #>> '{data,race,status}', '')) AS source_status,
        COUNT(re.id) FILTER (WHERE NOT re.scratched)::int AS expected_entries,
        COUNT(rr.id) FILTER (WHERE COALESCE(rr.result_quality, 'verified') = 'verified')::int AS valid_result_rows,
        COUNT(rr.id) FILTER (WHERE COALESCE(rr.result_quality, 'verified') <> 'verified')::int AS invalid_result_rows
    FROM tab_event_payloads_current tep
    JOIN races r ON r.external_race_id = tep.external_race_id
    LEFT JOIN race_entries re ON re.race_id = r.id
    LEFT JOIN race_results rr ON rr.race_entry_id = re.id
    GROUP BY r.id, r.status, tep.payload
)
INSERT INTO race_data_quality (
    race_id, observed_at, current_status, source_status, expected_entries,
    valid_result_rows, invalid_result_rows, issue_code, details
)
SELECT
    race_id, now(), current_status, source_status, expected_entries,
    valid_result_rows, invalid_result_rows,
    CASE
        WHEN invalid_result_rows > 0 THEN 'invalid_result_rows'
        WHEN source_status IN ('final', 'closed') AND valid_result_rows < expected_entries THEN 'partial_results'
        ELSE 'ok'
    END,
    jsonb_build_object('complete_result_set', expected_entries > 0 AND valid_result_rows = expected_entries)
FROM counts
ON CONFLICT (race_id) DO UPDATE SET
    observed_at = EXCLUDED.observed_at,
    current_status = EXCLUDED.current_status,
    source_status = EXCLUDED.source_status,
    expected_entries = EXCLUDED.expected_entries,
    valid_result_rows = EXCLUDED.valid_result_rows,
    invalid_result_rows = EXCLUDED.invalid_result_rows,
    issue_code = EXCLUDED.issue_code,
    details = EXCLUDED.details;

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
    JOIN tab_event_import_ids imported ON imported.external_race_id = r.external_race_id
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

WITH entry_src AS (
    SELECT
        race->>'event_id' AS external_race_id,
        tep.fetched_at AS captured_at,
        runner
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL (SELECT tep.payload #> '{data,race}' AS race) race_doc
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,runners}') = 'array' THEN tep.payload #> '{data,runners}' ELSE '[]'::jsonb END) AS runner
    WHERE runner->>'entrant_id' IS NOT NULL
)
INSERT INTO odds_snapshots (race_id, race_entry_id, captured_at, source, win_price, place_price, win_sp, place_sp, market_status)
SELECT
    r.id,
    re.id,
    entry_src.captured_at,
    'tab_affiliate_event',
    CASE WHEN NULLIF(entry_src.runner #>> '{odds,fixed_win}', '')::numeric > 0
        THEN NULLIF(entry_src.runner #>> '{odds,fixed_win}', '')::numeric END,
    CASE WHEN NULLIF(entry_src.runner #>> '{odds,fixed_place}', '')::numeric > 0
        THEN NULLIF(entry_src.runner #>> '{odds,fixed_place}', '')::numeric END,
    CASE WHEN NULLIF(entry_src.runner #>> '{odds,fixed_win}', '')::numeric > 0
        THEN NULLIF(entry_src.runner #>> '{odds,fixed_win}', '')::numeric END,
    CASE WHEN NULLIF(entry_src.runner #>> '{odds,fixed_place}', '')::numeric > 0
        THEN NULLIF(entry_src.runner #>> '{odds,fixed_place}', '')::numeric END,
    r.status
FROM entry_src
JOIN races r ON r.external_race_id = entry_src.external_race_id
JOIN runners run ON run.external_runner_id = entry_src.runner->>'entrant_id'
JOIN race_entries re ON re.race_id = r.id AND re.runner_id = run.id
WHERE NULLIF(entry_src.runner #>> '{odds,fixed_win}', '')::numeric > 0
ON CONFLICT DO NOTHING;

WITH entry_src AS (
    SELECT
        race->>'event_id' AS external_race_id,
        tep.fetched_at AS captured_at,
        runner
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL (SELECT tep.payload #> '{data,race}' AS race) race_doc
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,runners}') = 'array' THEN tep.payload #> '{data,runners}' ELSE '[]'::jsonb END) AS runner
    WHERE runner->>'entrant_id' IS NOT NULL
)
INSERT INTO fixed_odds_ticks (race_id, race_entry_id, price, source, captured_at, time_to_jump_s)
SELECT
    r.id,
    re.id,
    NULLIF(entry_src.runner #>> '{odds,fixed_win}', '')::numeric,
    'tab_affiliate_event',
    entry_src.captured_at,
    CASE WHEN r.scheduled_start_time IS NULL THEN NULL ELSE EXTRACT(EPOCH FROM (r.scheduled_start_time - entry_src.captured_at))::int END
FROM entry_src
JOIN races r ON r.external_race_id = entry_src.external_race_id
JOIN runners run ON run.external_runner_id = entry_src.runner->>'entrant_id'
JOIN race_entries re ON re.race_id = r.id AND re.runner_id = run.id
WHERE NULLIF(entry_src.runner #>> '{odds,fixed_win}', '')::numeric > 0
ON CONFLICT DO NOTHING;

-- TAB supplies real timestamped fluctuations. Persist those timestamps rather
-- than assigning scheduled jump time to every observation.
WITH fluc_src AS (
    SELECT
        race->>'event_id' AS external_race_id,
        runner->>'entrant_id' AS external_runner_id,
        fluc
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL (SELECT tep.payload #> '{data,race}' AS race) race_doc
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,runners}') = 'array' THEN tep.payload #> '{data,runners}' ELSE '[]'::jsonb END) AS runner
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(runner #> '{flucs_with_timestamp,last_six}') = 'array' THEN runner #> '{flucs_with_timestamp,last_six}' ELSE '[]'::jsonb END) AS fluc
    WHERE runner->>'entrant_id' IS NOT NULL
      AND NULLIF(fluc->>'fluc', '') IS NOT NULL
      AND NULLIF(fluc->>'timestamp', '') IS NOT NULL
      AND fluc->>'timestamp' NOT LIKE '0001-%'
)
INSERT INTO fixed_odds_ticks (race_id, race_entry_id, price, source, captured_at, time_to_jump_s)
SELECT
    r.id,
    re.id,
    (fluc_src.fluc->>'fluc')::numeric,
    'tab_affiliate_fluc',
    (fluc_src.fluc->>'timestamp')::timestamptz,
    CASE WHEN r.scheduled_start_time IS NULL THEN NULL ELSE EXTRACT(EPOCH FROM (r.scheduled_start_time - (fluc_src.fluc->>'timestamp')::timestamptz))::int END
FROM fluc_src
JOIN races r ON r.external_race_id = fluc_src.external_race_id
JOIN runners run ON run.external_runner_id = fluc_src.external_runner_id
JOIN race_entries re ON re.race_id = r.id AND re.runner_id = run.id
WHERE (fluc_src.fluc->>'fluc')::numeric > 0
ON CONFLICT DO NOTHING;

WITH ordered AS (
    SELECT
        fot.race_id,
        fot.race_entry_id,
        fot.captured_at,
        fot.time_to_jump_s,
        fot.price,
        LAG(fot.price) OVER (PARTITION BY fot.race_entry_id ORDER BY fot.captured_at, fot.id) AS previous_price
    FROM fixed_odds_ticks fot
    JOIN races r ON r.id = fot.race_id
    JOIN tab_event_import_ids imported ON imported.external_race_id = r.external_race_id
    WHERE fot.source IN ('tab_affiliate_event', 'tab_affiliate_fluc')
      AND fot.price > 0
), movements AS (
    SELECT *, ((price - previous_price) / NULLIF(previous_price, 0) * 100.0)::real AS movement_pct
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
    JOIN races r ON r.id = fot.race_id
    JOIN tab_event_import_ids imported ON imported.external_race_id = r.external_race_id
    WHERE fot.source IN ('tab_affiliate_event', 'tab_affiliate_fluc')
      AND fot.price > 0
    GROUP BY fot.race_id, fot.race_entry_id
), movement_counts AS (
    SELECT race_entry_id,
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
    s.race_id, s.race_entry_id, s.opening_price, s.closing_price, s.min_price, s.max_price,
    (s.max_price - s.min_price)::real,
    ((s.closing_price - s.opening_price) / NULLIF(s.opening_price, 0) * 100.0)::real,
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

WITH pool_src AS (
    SELECT
        tep.external_race_id,
        tep.fetched_at AS captured_at,
        pool
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,tote_pools}') = 'array' THEN tep.payload #> '{data,tote_pools}' ELSE '[]'::jsonb END) AS pool
)
INSERT INTO tote_pools (race_id, pool_type, pool_size, captured_at, dividend)
SELECT
    r.id,
    lower(regexp_replace(pool_src.pool->>'product_type', '\s+', '_', 'g')),
    NULLIF(pool_src.pool->>'total', '')::numeric,
    pool_src.captured_at,
    NULL
FROM pool_src
JOIN races r ON r.external_race_id = pool_src.external_race_id
WHERE pool_src.pool->>'product_type' IS NOT NULL
ON CONFLICT DO NOTHING;

WITH signal_src AS (
    SELECT
        tep.external_race_id,
        tep.fetched_at AS captured_at,
        race,
        runner,
        COALESCE(NULLIF((money->>'hold_percentage'), '')::real, 0) AS hold_pct,
        COALESCE(NULLIF((money->>'bet_percentage'), '')::real, 0) AS bet_pct
    FROM tab_event_payloads_current tep
    CROSS JOIN LATERAL (SELECT tep.payload #> '{data,race}' AS race) race_doc
    CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,money_tracker,entrants}') = 'array' THEN tep.payload #> '{data,money_tracker,entrants}' ELSE '[]'::jsonb END) AS money
    JOIN LATERAL (
        SELECT runner
        FROM jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,runners}') = 'array' THEN tep.payload #> '{data,runners}' ELSE '[]'::jsonb END) AS runner
        WHERE runner->>'entrant_id' = money->>'entrant_id'
        LIMIT 1
    ) matched ON true
    WHERE (COALESCE(NULLIF((money->>'hold_percentage'), '')::real, 0) > 0
        OR COALESCE(NULLIF((money->>'bet_percentage'), '')::real, 0) > 0)
), ranked AS (
    SELECT DISTINCT ON (external_race_id, runner->>'entrant_id')
        *
    FROM signal_src
    ORDER BY external_race_id, runner->>'entrant_id', (hold_pct + bet_pct) DESC
)
INSERT INTO market_signals (race_id, race_entry_id, signal_type, magnitude, detected_at, time_to_jump_s, evidence_json)
SELECT
    r.id,
    re.id,
    CASE WHEN ranked.bet_pct >= ranked.hold_pct THEN 'late_money' ELSE 'smart_money' END,
    LEAST(1.0, GREATEST(ranked.hold_pct, ranked.bet_pct) / 100.0),
    ranked.captured_at,
    CASE WHEN r.scheduled_start_time IS NULL THEN NULL ELSE EXTRACT(EPOCH FROM (r.scheduled_start_time - ranked.captured_at))::int END,
    jsonb_build_object('source', 'tab_money_tracker', 'hold_percentage', ranked.hold_pct, 'bet_percentage', ranked.bet_pct)
FROM ranked
JOIN races r ON r.external_race_id = ranked.external_race_id
JOIN runners run ON run.external_runner_id = ranked.runner->>'entrant_id'
JOIN race_entries re ON re.race_id = r.id AND re.runner_id = run.id
WHERE GREATEST(ranked.hold_pct, ranked.bet_pct) >= 5
  AND ranked.captured_at >= current_date - interval '7 days'
ON CONFLICT DO NOTHING;

WITH recent_smart_signals AS (
    SELECT DISTINCT ON (ms.race_id, ms.race_entry_id, ms.detected_at)
        ms.race_id,
        ms.race_entry_id,
        'tab_money_tracker'::text AS indicator_type,
        LEAST(0.95, 0.55 + ms.magnitude) AS confidence,
        ms.detected_at
    FROM market_signals ms
    WHERE ms.signal_type = 'smart_money'
      AND ms.detected_at >= current_date - interval '2 days'
    ORDER BY ms.race_id, ms.race_entry_id, ms.detected_at, ms.magnitude DESC
)
INSERT INTO smart_money_indicators (race_id, race_entry_id, indicator_type, confidence, detected_at)
SELECT
    s.race_id,
    s.race_entry_id,
    s.indicator_type,
    s.confidence,
    s.detected_at
FROM recent_smart_signals s
WHERE NOT EXISTS (
    SELECT 1
    FROM smart_money_indicators existing
    WHERE existing.race_id = s.race_id
      AND existing.race_entry_id = s.race_entry_id
      AND existing.indicator_type = s.indicator_type
      AND existing.detected_at = s.detected_at
)
ON CONFLICT (race_id, race_entry_id, indicator_type, detected_at) DO UPDATE
SET confidence = GREATEST(smart_money_indicators.confidence, EXCLUDED.confidence);

BEGIN;
SELECT pg_advisory_xact_lock(hashtext('betman_horse_scores_writer'));

WITH score_src AS (
    SELECT
        r.id AS race_id,
        re.id AS race_entry_id,
        run.id AS runner_id,
        re.barrier_number,
        re.final_position,
        COALESCE(NULLIF(os.win_price, 0), NULL) AS market_price,
        COALESCE(re.career_wins, 0) AS career_wins,
        COALESCE(re.career_starts, 0) AS career_starts,
        re.gear_changes_json
    FROM race_entries re
    JOIN races r ON r.id = re.race_id
    JOIN tab_event_import_ids imported ON imported.external_race_id = r.external_race_id
    JOIN runners run ON run.id = re.runner_id
    LEFT JOIN LATERAL (
        SELECT win_price
        FROM odds_snapshots os
        WHERE os.race_entry_id = re.id
          AND win_price > 0
        ORDER BY captured_at DESC
        LIMIT 1
    ) os ON true
    WHERE re.scratched = false
)
INSERT INTO horse_scores (
    race_id,
    race_entry_id,
    runner_id,
    bc_score,
    gas_score,
    mis_score,
    sis_score,
    hfs_score,
    was_score,
    bms_score,
    tbi_score,
    value_score,
    alpha_score,
    market_price,
    implied_probability,
    betman_probability,
    calculated_at,
    model_version
)
SELECT
    race_id,
    race_entry_id,
    runner_id,
    CASE WHEN career_starts > 0 THEN LEAST(100, 45 + (career_wins::real / NULLIF(career_starts, 0)) * 120) ELSE NULL END,
    CASE WHEN barrier_number BETWEEN 1 AND 4 THEN 68 WHEN barrier_number BETWEEN 5 AND 8 THEN 58 WHEN barrier_number IS NULL THEN NULL ELSE 48 END,
    CASE WHEN market_price IS NOT NULL THEN LEAST(100, 100 / market_price) ELSE NULL END,
    CASE WHEN gear_changes_json::text ILIKE '%Trainer / Jockey Combo%' THEN 72 ELSE 50 END,
    NULL,
    NULL,
    NULL,
    NULL,
    CASE WHEN market_price IS NOT NULL THEN LEAST(100, 100 / market_price) ELSE NULL END,
    LEAST(100, GREATEST(0,
        COALESCE(CASE WHEN market_price IS NOT NULL THEN 100 / market_price ELSE NULL END, 45)
        + COALESCE(CASE WHEN barrier_number BETWEEN 1 AND 4 THEN 8 WHEN barrier_number BETWEEN 5 AND 8 THEN 3 ELSE -2 END, 0)
        + CASE WHEN gear_changes_json::text ILIKE '%Trainer / Jockey Combo%' THEN 5 ELSE 0 END
    )),
    market_price,
    CASE WHEN market_price IS NOT NULL AND market_price > 0 THEN round((100.0 / market_price)::numeric, 4)::real ELSE NULL END,
    CASE WHEN market_price IS NOT NULL AND market_price > 0 THEN round(LEAST(95.0, GREATEST(1.0, (100.0 / market_price) + CASE WHEN barrier_number BETWEEN 1 AND 4 THEN 2 ELSE 0 END))::numeric, 4)::real ELSE NULL END,
    now(),
    'tab_import_v1_derived'
FROM score_src
ON CONFLICT (race_id, race_entry_id) DO UPDATE
SET bc_score = EXCLUDED.bc_score,
    gas_score = EXCLUDED.gas_score,
    mis_score = EXCLUDED.mis_score,
    sis_score = EXCLUDED.sis_score,
    value_score = EXCLUDED.value_score,
    alpha_score = EXCLUDED.alpha_score,
    market_price = EXCLUDED.market_price,
    implied_probability = EXCLUDED.implied_probability,
    betman_probability = EXCLUDED.betman_probability,
    calculated_at = EXCLUDED.calculated_at,
    model_version = EXCLUDED.model_version;

COMMIT;

INSERT INTO race_summaries (race_id, summary_text, key_moments, winner_name, margin_description, model_version, generated_at)
SELECT
    r.id,
    COALESCE(NULLIF(tep.payload #>> '{data,race,comment}', ''), 'TAB race payload imported.'),
    '[]'::jsonb,
    winner.name,
    NULL,
    'tab_affiliate_import',
    now()
FROM tab_event_payloads_current tep
JOIN races r ON r.external_race_id = tep.external_race_id
LEFT JOIN LATERAL (
    SELECT res->>'name' AS name
    FROM jsonb_array_elements(CASE WHEN jsonb_typeof(tep.payload #> '{data,results}') = 'array' THEN tep.payload #> '{data,results}' ELSE '[]'::jsonb END) AS res
    WHERE res->>'position' = '1'
    LIMIT 1
) winner ON true
WHERE NULLIF(tep.payload #>> '{data,race,comment}', '') IS NOT NULL
ON CONFLICT (race_id) DO UPDATE
SET summary_text = EXCLUDED.summary_text,
    winner_name = EXCLUDED.winner_name,
    generated_at = EXCLUDED.generated_at;

ANALYZE meetings;
ANALYZE races;
ANALYZE runners;
ANALYZE race_entries;
ANALYZE odds_snapshots;
ANALYZE fixed_odds_ticks;
ANALYZE market_signals;
ANALYZE horse_scores;
