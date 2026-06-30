#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE=${BETMAN_DATA_TAB_POLLER_LOCK:-/run/betman-data-tab-poller.lock}
ROOT=${BETMAN_DATA_ROOT:-/opt/betman/betman_data}
ENV_FILE=${BETMAN_DATA_ENV_FILE:-/etc/betman/betman-data.env}
TIMEZONE=${BETMAN_DATA_TIMEZONE:-Pacific/Auckland}
COUNTRIES=${BETMAN_DATA_TAB_COUNTRIES:-NZ,AUS}
WORKERS=${BETMAN_DATA_TAB_WORKERS:-8}
RETRIES=${BETMAN_DATA_TAB_RETRIES:-2}
LOOKBACK_DAYS=${BETMAN_DATA_TAB_LOOKBACK_DAYS:-0}
LOOKAHEAD_DAYS=${BETMAN_DATA_TAB_LOOKAHEAD_DAYS:-1}

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "betman-data poller already running; skipping"
  exit 0
fi

cd "${ROOT}"

if [[ -f "${ENV_FILE}" ]]; then
  while IFS='=' read -r key value; do
    [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    case "${key}" in
      TAB_*|BETMAN_CONTACT_EMAIL)
        export "${key}=${value}"
        ;;
    esac
  done < "${ENV_FILE}"
fi

today=$(TZ="${TIMEZONE}" date +%F)
start=${1:-$(TZ="${TIMEZONE}" date -d "${today} - ${LOOKBACK_DAYS} day" +%F)}
end=${2:-$(TZ="${TIMEZONE}" date -d "${today} + ${LOOKAHEAD_DAYS} day" +%F)}
run_id=$(date -u +%Y%m%dT%H%M%SZ)
jsonl=$(mktemp "/tmp/betman-tab-events-${run_id}.XXXXXX.jsonl")
sql=$(mktemp "/tmp/betman-tab-load-${run_id}.XXXXXX.sql")

cleanup() {
  rm -f "${jsonl}" "${sql}"
}
trap cleanup EXIT

echo "Polling TAB thoroughbred events ${start}..${end} (${COUNTRIES})"
python3 scripts/fetch_tab_event_history.py \
  --start "${start}" \
  --end "${end}" \
  --countries "${COUNTRIES}" \
  --type T \
  --race-types T \
  --workers "${WORKERS}" \
  --retries "${RETRIES}" \
  --out "${jsonl}"

if [[ ! -s "${jsonl}" ]]; then
  echo "No thoroughbred TAB events returned"
  exit 0
fi

escaped_jsonl=${jsonl//\\/\\\\}
escaped_jsonl=${escaped_jsonl//\//\\/}
sed "s/__TAB_EVENT_JSONL__/${escaped_jsonl}/g" scripts/load_tab_event_payloads.sql > "${sql}"
chmod 644 "${jsonl}" "${sql}"

sudo -u postgres psql -d betman_data -v ON_ERROR_STOP=1 -f "${sql}"
loaded_count=$(wc -l < "${jsonl}")
echo "Loaded ${loaded_count} thoroughbred TAB event payloads"
