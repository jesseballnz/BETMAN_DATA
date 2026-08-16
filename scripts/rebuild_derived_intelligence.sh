#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
psql -v ON_ERROR_STOP=1 -f "${SCRIPT_DIR}/rebuild_derived_intelligence.sql"
