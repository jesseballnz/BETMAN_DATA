#!/usr/bin/env bash
set -euo pipefail

ROOT=${BETMAN_DATA_ROOT:-/opt/betman/betman_data}
DB=${BETMAN_DATA_DB:-betman_data}
PSQL_USER=${BETMAN_DATA_PSQL_USER:-postgres}
LOCK_FILE=${BETMAN_DATA_COMPACT_LOCK:-/run/betman-data-storage-compact.lock}
MIN_TABLE_BYTES=${BETMAN_DATA_COMPACT_MIN_TABLE_BYTES:-536870912}
EMERGENCY_FREE_PCT=${BETMAN_DATA_COMPACT_EMERGENCY_FREE_PCT:-10}
ALLOW_EMERGENCY_TRUNCATE=${BETMAN_DATA_COMPACT_ALLOW_EMERGENCY_TRUNCATE:-0}

TABLES=(
  odds_snapshots
  fixed_odds_ticks
  market_signals
  tote_pools
  smart_money_indicators
)

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "betman-data storage compaction already running; skipping"
  exit 0
fi

cd "${ROOT}"

psql_cmd() {
  if [[ -n "${PSQL_USER}" ]]; then
    sudo -u "${PSQL_USER}" psql -d "${DB}" "$@"
  else
    psql -d "${DB}" "$@"
  fi
}

root_free_pct() {
  df -P / | awk 'NR == 2 {gsub("%", "", $5); print 100 - $5}'
}

echo "BETMAN_DATA storage compaction started at $(date -Is)"
echo "Minimum table size: ${MIN_TABLE_BYTES} bytes"
echo "Emergency free-space floor: ${EMERGENCY_FREE_PCT}%"

free_pct=$(root_free_pct)
echo "Root filesystem free: ${free_pct}%"

if [[ "${ALLOW_EMERGENCY_TRUNCATE}" =~ ^(1|true|yes|on)$ ]] && (( free_pct < EMERGENCY_FREE_PCT )); then
  echo "Root filesystem below emergency floor; resetting regenerated high-frequency fact tables."
  psql_cmd -X -P pager=off -v ON_ERROR_STOP=1 <<'SQL'
SET lock_timeout = 10000;
TRUNCATE TABLE odds_snapshots, fixed_odds_ticks, market_signals, tote_pools, smart_money_indicators;
ANALYZE odds_snapshots;
ANALYZE fixed_odds_ticks;
ANALYZE market_signals;
ANALYZE tote_pools;
ANALYZE smart_money_indicators;
CHECKPOINT;
SQL
  df -h /
  echo "BETMAN_DATA emergency compaction finished at $(date -Is)"
  exit 0
fi

mapfile -t candidates < <(
  psql_cmd -X -At -P pager=off -v min_table_bytes="${MIN_TABLE_BYTES}" <<'SQL'
SELECT relid::regclass::text
FROM pg_stat_user_tables
WHERE relid::regclass::text = ANY(ARRAY[
    'odds_snapshots',
    'fixed_odds_ticks',
    'market_signals',
    'tote_pools',
    'smart_money_indicators'
  ])
  AND pg_total_relation_size(relid) >= :min_table_bytes::bigint
ORDER BY pg_total_relation_size(relid) DESC;
SQL
)

if (( ${#candidates[@]} == 0 )); then
  echo "No high-frequency tables exceed compaction threshold."
  psql_cmd -X -P pager=off -v ON_ERROR_STOP=1 <<'SQL'
VACUUM (ANALYZE) odds_snapshots;
VACUUM (ANALYZE) fixed_odds_ticks;
VACUUM (ANALYZE) market_signals;
VACUUM (ANALYZE) tote_pools;
VACUUM (ANALYZE) smart_money_indicators;
SQL
  exit 0
fi

printf 'Compaction candidates: %s\n' "${candidates[*]}"

for table in "${candidates[@]}"; do
  allowed=0
  for known in "${TABLES[@]}"; do
    if [[ "${table}" == "${known}" ]]; then
      allowed=1
      break
    fi
  done
  if (( allowed == 0 )); then
    echo "Refusing unexpected table name: ${table}" >&2
    exit 1
  fi

  echo "VACUUM FULL ${table}"
  psql_cmd -X -P pager=off -v ON_ERROR_STOP=1 -c "VACUUM (FULL, ANALYZE) ${table};"
done

psql_cmd -X -P pager=off -v ON_ERROR_STOP=1 <<'SQL'
CHECKPOINT;
SELECT relid::regclass AS relation,
       pg_size_pretty(pg_total_relation_size(relid)) AS total
FROM pg_stat_user_tables
WHERE relid::regclass::text = ANY(ARRAY[
    'odds_snapshots',
    'fixed_odds_ticks',
    'market_signals',
    'tote_pools',
    'smart_money_indicators'
  ])
ORDER BY pg_total_relation_size(relid) DESC;
SQL

df -h /
echo "BETMAN_DATA storage compaction finished at $(date -Is)"
