# BETMAN Libs

Shared libraries used across BETMAN_DATA services.

```
libs/
  db/       — Database connection helpers and query utilities
  schemas/  — Shared Pydantic schemas for inter-service data contracts
  media/    — Media processing utilities (FFmpeg wrappers, HLS helpers)
  signals/  — Signal classification utilities shared between workers
```

These libraries are intended to be installed as editable packages within each service's
virtual environment to avoid code duplication.

## Current Libraries

| Directory | Purpose |
|---|---|
| `libs/db/` | asyncpg connection pool helpers, query builders, migration utilities |
| `libs/schemas/` | Shared Pydantic models for events published to Redis pub/sub |
| `libs/media/` | FFmpeg subprocess wrappers, HLS playlist parsing, segment metadata extraction |
| `libs/signals/` | Signal classification constants, threshold definitions, score normalisation helpers |

## Usage

Each library has its own `pyproject.toml`. Install with:

```bash
pip install -e libs/db
pip install -e libs/schemas
# etc.
```

All services list the relevant libs as local path dependencies in their own `pyproject.toml`.
