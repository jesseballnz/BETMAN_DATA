#!/usr/bin/env bash
set -euo pipefail

ROOT=${BETMAN_DATA_ROOT:-/opt/betman/betman_data}
DB=${BETMAN_DATA_DB:-betman_data}
PSQL_USER=${BETMAN_DATA_PSQL_USER:-postgres}
RETENTION_DAYS=${BETMAN_DATA_HIGH_FREQUENCY_RETENTION_DAYS:-7}
SMART_MONEY_RETENTION_DAYS=${BETMAN_DATA_SMART_MONEY_RETENTION_DAYS:-2}
PRUNE_BATCH_SIZE=${BETMAN_DATA_PRUNE_BATCH_SIZE:-50000}
PRUNE_MAX_BATCHES=${BETMAN_DATA_PRUNE_MAX_BATCHES:-200}
LOCK_FILE=${BETMAN_DATA_RETENTION_LOCK:-/run/betman-data-retention-prune.lock}

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "betman-data retention prune already running; skipping"
  exit 0
fi

cd "${ROOT}"

echo "BETMAN_DATA retention prune started at $(date -Is)"
echo "High-frequency retention: ${RETENTION_DAYS} days"
echo "Smart money retention: ${SMART_MONEY_RETENTION_DAYS} days"
echo "Batch size: ${PRUNE_BATCH_SIZE}; max batches per table: ${PRUNE_MAX_BATCHES}"

if [[ -n "${PSQL_USER}" ]]; then
  PSQL=(sudo -u "${PSQL_USER}" psql -d "${DB}")
else
  PSQL=(psql -d "${DB}")
fi

"${PSQL[@]}" \
  -v ON_ERROR_STOP=1 \
  -v high_frequency_retention_days="${RETENTION_DAYS}" \
  -v smart_money_retention_days="${SMART_MONEY_RETENTION_DAYS}" \
  -v prune_batch_size="${PRUNE_BATCH_SIZE}" \
  -v prune_max_batches="${PRUNE_MAX_BATCHES}" \
  < scripts/prune_data_retention.sql

echo "BETMAN_DATA retention prune finished at $(date -Is)"
