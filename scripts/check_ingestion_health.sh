#!/usr/bin/env bash
set -euo pipefail

DB=${BETMAN_DATA_DB:-betman_data}
PSQL_USER=${BETMAN_DATA_PSQL_USER:-postgres}
MAX_FRESHNESS_SECONDS=${BETMAN_DATA_MAX_FRESHNESS_SECONDS:-900}
MAX_DISK_USED_PCT=${BETMAN_DATA_MAX_DISK_USED_PCT:-80}
MIN_UPCOMING_FEATURE_COVERAGE=${BETMAN_DATA_MIN_UPCOMING_FEATURE_COVERAGE:-0.95}

if [[ -n "${PSQL_USER}" ]]; then
  PSQL=(sudo -u "${PSQL_USER}" psql -d "${DB}")
else
  PSQL=(psql -d "${DB}")
fi

disk_used_pct=$(df -P / | awk 'NR == 2 {gsub("%", "", $5); print $5}')
poller_result=$(systemctl show betman-data-tab-poller.service -p Result --value 2>/dev/null || true)
poller_result=${poller_result:-unknown}

healthy=$("${PSQL[@]}" -X -At -P pager=off -v ON_ERROR_STOP=1 \
  -v max_freshness_seconds="${MAX_FRESHNESS_SECONDS}" \
  -v max_disk_used_pct="${MAX_DISK_USED_PCT}" \
  -v disk_used_pct="${disk_used_pct}" \
  -v poller_result="${poller_result}" \
  -v min_feature_coverage="${MIN_UPCOMING_FEATURE_COVERAGE}" <<'SQL'
WITH freshness AS (
    SELECT COALESCE(EXTRACT(EPOCH FROM (now() - MAX(fetched_at)))::int, 2147483647) AS seconds
    FROM tab_event_payloads
), countries AS (
    SELECT jsonb_object_agg(country, payloads) AS value
    FROM (
        SELECT country, COUNT(*) AS payloads
        FROM tab_event_payloads
        WHERE fetched_at >= now() - interval '14 days'
        GROUP BY country
    ) x
), upcoming AS (
    SELECT
        COUNT(*) FILTER (WHERE NOT re.scratched) AS entries,
        COUNT(raf.id) FILTER (WHERE NOT re.scratched) AS features,
        COUNT(p.id) FILTER (WHERE NOT re.scratched) AS pedigrees
    FROM races r
    JOIN race_entries re ON re.race_id = r.id
    LEFT JOIN race_analysis_features raf ON raf.race_entry_id = re.id
    LEFT JOIN pedigrees p ON p.runner_id = re.runner_id
    WHERE r.scheduled_start_time BETWEEN now() - interval '30 minutes' AND now() + interval '48 hours'
), coverage AS (
    SELECT
        entries,
        features,
        pedigrees,
        -- No races in the next 48 hours is a valid quiet-calendar state, not
        -- missing ingestion. Coverage becomes applicable as soon as entries exist.
        CASE WHEN entries = 0 THEN 1 ELSE features::numeric / entries END AS feature_ratio,
        CASE WHEN entries = 0 THEN 1 ELSE pedigrees::numeric / entries END AS pedigree_ratio,
        (SELECT COUNT(*) FROM track_condition_readings WHERE recorded_at >= now() - interval '14 days') AS recent_conditions,
        (SELECT COUNT(*) FROM odds_analytics WHERE updated_at >= now() - interval '14 days') AS recent_odds_analytics,
        (SELECT COUNT(*) FROM odds_movements WHERE detected_at >= now() - interval '14 days') AS recent_odds_movements
    FROM upcoming
), checks AS (
    SELECT
        f.seconds,
        COALESCE(c.value, '{}'::jsonb) AS countries,
        cov.*,
        (f.seconds <= :max_freshness_seconds::int) AS freshness_ok,
        (COALESCE((c.value->>'NZ')::int, 0) > 0) AS nz_ok,
        (COALESCE((c.value->>'AUS')::int, 0) > 0) AS aus_ok,
        (COALESCE((c.value->>'HK')::int, 0) > 0) AS hk_ok,
        (cov.feature_ratio >= :min_feature_coverage::numeric) AS features_ok,
        (cov.pedigree_ratio >= 0.95) AS pedigrees_ok,
        (cov.recent_conditions > 0) AS conditions_ok,
        (cov.recent_odds_analytics > 0) AS analytics_ok,
        (:'poller_result' = 'success') AS poller_ok,
        (:disk_used_pct::int <= :max_disk_used_pct::int) AS disk_ok
    FROM freshness f CROSS JOIN countries c CROSS JOIN coverage cov
), inserted AS (
    INSERT INTO ingestion_health_snapshots (
        checked_at, healthy, payload_freshness_seconds, countries, coverage, storage,
        poller_result, failures
    )
    SELECT
        now(),
        freshness_ok AND nz_ok AND aus_ok AND hk_ok AND features_ok
            AND pedigrees_ok AND conditions_ok AND analytics_ok AND poller_ok AND disk_ok,
        seconds,
        countries,
        jsonb_build_object(
            'upcoming_entries', entries,
            'analysis_features', features,
            'feature_ratio', feature_ratio,
            'pedigrees', pedigrees,
            'pedigree_ratio', pedigree_ratio,
            'recent_track_conditions', recent_conditions,
            'recent_odds_analytics', recent_odds_analytics,
            'recent_odds_movements', recent_odds_movements
        ),
        jsonb_build_object('disk_used_pct', :disk_used_pct::int),
        :'poller_result',
        to_jsonb(array_remove(ARRAY[
            CASE WHEN NOT freshness_ok THEN 'payload_stale' END,
            CASE WHEN NOT nz_ok THEN 'nz_missing' END,
            CASE WHEN NOT aus_ok THEN 'aus_missing' END,
            CASE WHEN NOT hk_ok THEN 'hk_missing_14d' END,
            CASE WHEN NOT features_ok THEN 'analysis_features_incomplete' END,
            CASE WHEN NOT pedigrees_ok THEN 'pedigrees_incomplete' END,
            CASE WHEN NOT conditions_ok THEN 'track_conditions_stale' END,
            CASE WHEN NOT analytics_ok THEN 'odds_analytics_stale' END,
            CASE WHEN NOT poller_ok THEN 'poller_failed' END,
            CASE WHEN NOT disk_ok THEN 'disk_pressure' END
        ], NULL))
    FROM checks
    RETURNING healthy
)
SELECT healthy FROM inserted;
SQL
)

echo "ingestion_health healthy=${healthy} disk_used_pct=${disk_used_pct} poller_result=${poller_result} checked_at=$(date -Is)"
if [[ "${healthy}" != "t" ]]; then
  exit 1
fi
