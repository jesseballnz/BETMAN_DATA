#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE=${BETMAN_DATA_TAB_POLLER_LOCK:-/run/betman-data-tab-poller.lock}
ROOT=${BETMAN_DATA_ROOT:-/opt/betman/betman_data}
ENV_FILE=${BETMAN_DATA_ENV_FILE:-/etc/betman/betman-data.env}

LOCK_DIR=""
if command -v flock >/dev/null 2>&1; then
  exec 9>"${LOCK_FILE}"
  if ! flock -n 9; then
    echo "betman-data poller already running; skipping"
    exit 0
  fi
else
  LOCK_DIR="${LOCK_FILE}.d"
  if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
    echo "betman-data poller already running; skipping"
    exit 0
  fi
fi

cd "${ROOT}"

if [[ -f "${ENV_FILE}" ]]; then
  while IFS='=' read -r key value; do
    [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    case "${key}" in
      TAB_*|BETMAN_DATA_TAB_*|BETMAN_CONTACT_EMAIL)
        export "${key}=${value}"
        ;;
    esac
  done < "${ENV_FILE}"
fi

TIMEZONE=${BETMAN_DATA_TIMEZONE:-Pacific/Auckland}
COUNTRIES=${BETMAN_DATA_TAB_COUNTRIES:-NZ,AUS,HK}
WORKERS=${BETMAN_DATA_TAB_WORKERS:-8}
RETRIES=${BETMAN_DATA_TAB_RETRIES:-2}
# Always revisit yesterday so late/finalised TAB results are reconciled after
# midnight and a transient failed poll cannot leave a permanent history gap.
LOOKBACK_DAYS=${BETMAN_DATA_TAB_LOOKBACK_DAYS:-1}
LOOKAHEAD_DAYS=${BETMAN_DATA_TAB_LOOKAHEAD_DAYS:-1}
RECONCILE_DAYS=${BETMAN_DATA_TAB_RECONCILE_DAYS:-14}

date_offset() {
  local base_date=$1
  local offset_days=$2
  python3 - "${base_date}" "${offset_days}" <<'PY'
from datetime import datetime, timedelta
import sys

base = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
print((base + timedelta(days=int(sys.argv[2]))).isoformat())
PY
}

today=$(TZ="${TIMEZONE}" date +%F)
start=${1:-$(TZ="${TIMEZONE}" date_offset "${today}" "-${LOOKBACK_DAYS}")}
end=${2:-$(TZ="${TIMEZONE}" date_offset "${today}" "+${LOOKAHEAD_DAYS}")}
run_id=$(date -u +%Y%m%dT%H%M%SZ)
jsonl=$(mktemp "/tmp/betman-tab-events-${run_id}.XXXXXX.jsonl")
sql=$(mktemp "/tmp/betman-tab-load-${run_id}.XXXXXX.sql")
reconcile_targets=$(mktemp "/tmp/betman-tab-reconcile-${run_id}.XXXXXX.tsv")

cleanup() {
  rm -f "${jsonl}" "${sql}" "${reconcile_targets}"
  if [[ -n "${LOCK_DIR}" ]]; then
    rmdir "${LOCK_DIR}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

PSQL_DB=${BETMAN_DATA_DB:-betman_data}
if [[ -n "${BETMAN_DATA_PSQL_USER:-}" ]]; then
  PSQL=(sudo -u "${BETMAN_DATA_PSQL_USER}" psql -d "${PSQL_DB}")
elif [[ "$(id -u)" = "0" ]] && id postgres >/dev/null 2>&1; then
  PSQL=(sudo -u postgres psql -d "${PSQL_DB}")
else
  PSQL=(psql -d "${PSQL_DB}")
fi

# Recheck exact unresolved historical events without replaying every race from
# the surrounding dates. The meetings listing supplies authoritative terminal
# states when an event-detail document is stuck at Open after abandonment.
"${PSQL[@]}" -X -At -F $'\t' -P pager=off -v ON_ERROR_STOP=1 \
  -v reconcile_days="${RECONCILE_DAYS}" >"${reconcile_targets}" <<'SQL'
SELECT DISTINCT r.external_race_id, m.jurisdiction, m.meeting_date
FROM races r
JOIN meetings m ON m.id = r.meeting_id
WHERE r.external_race_id IS NOT NULL
  AND m.jurisdiction IN ('NZ', 'AUS', 'HK')
  AND m.meeting_date >= current_date - :reconcile_days::int
  AND (
    (
      r.status = 'scheduled'
      AND m.status <> 'abandoned'
      AND r.scheduled_start_time < now() - interval '6 hours'
    )
    OR (
      r.status = 'finished'
      AND COALESCE(r.actual_start_time, r.scheduled_start_time) < now() - interval '45 minutes'
      AND (
        NOT EXISTS (SELECT 1 FROM race_results rr WHERE rr.race_id = r.id)
        OR EXISTS (
          SELECT 1
          FROM race_results rr
          JOIN race_entries re ON re.id = rr.race_entry_id
          WHERE rr.race_id = r.id
            AND rr.finish_position > 0
            AND re.final_position IS DISTINCT FROM rr.finish_position
        )
      )
    )
  )
ORDER BY m.meeting_date, m.jurisdiction, r.external_race_id;
SQL

echo "Polling TAB thoroughbred events ${start}..${end} (${COUNTRIES})"
python3 scripts/fetch_tab_event_history.py \
  --start "${start}" \
  --end "${end}" \
  --countries "${COUNTRIES}" \
  --type T \
  --race-types T \
  --workers "${WORKERS}" \
  --retries "${RETRIES}" \
  --reconcile-targets "${reconcile_targets}" \
  --out "${jsonl}"

if [[ ! -s "${jsonl}" ]]; then
  echo "No thoroughbred TAB events returned"
  exit 0
fi

escaped_jsonl=${jsonl//\\/\\\\}
escaped_jsonl=${escaped_jsonl//\//\\/}
sed "s/__TAB_EVENT_JSONL__/${escaped_jsonl}/g" scripts/load_tab_event_payloads.sql > "${sql}"
chmod 644 "${jsonl}" "${sql}"

"${PSQL[@]}" -v ON_ERROR_STOP=1 -f "${sql}"
loaded_count=$(wc -l < "${jsonl}")
echo "Loaded ${loaded_count} thoroughbred TAB event payloads"
