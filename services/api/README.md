# BETMAN Data API — Service

The BETMAN Data API is the query interface for the entire BETMAN data platform.
It exposes races, runners, signals, commentary replay, barrier analysis, weather intelligence,
market signals, discovery patterns, proprietary BETMAN scores, and the skin engine for
multi-tenant OEM licensing.

## Tech Stack

- **Python 3.11+**
- **FastAPI** — async web framework
- **asyncpg** — async PostgreSQL driver
- **Redis** — live state cache and pub/sub
- **pydantic-settings** — typed configuration
- **structlog** — structured JSON logging

## Project Layout

```
services/api/
  app/
    main.py           — FastAPI app, lifespan, middleware, router registration
    config.py         — pydantic-settings configuration
    middleware.py     — TenantMiddleware + RequestLoggingMiddleware
    routers/
      health.py       — GET /v1/health
      feeds.py        — Feed listing
      races.py        — Race detail, replay, story, odds drift, barrier context
      runners.py      — Runner detail and form history
      tracks.py       — Barrier analysis, heatmap, weather, conditions
      events.py       — Derived race timeline events
      search.py       — OCR, transcript, similarity search
      skins.py        — Tenant skin resolution
      intelligence.py — BETMAN scores, pre-race intelligence, knowledge graph
      pedigree.py     — Bloodline performance and sire affinities
      market.py       — Steamers, drifters, smart money, odds ticks
      discovery.py    — Discovered patterns and generated signals
      admin.py        — Admin CRUD for tenants, skins, weather stations, API keys
  Dockerfile
  pyproject.toml
  .env.example
```

## Running Locally

### Prerequisites

Make sure the infrastructure is up (Postgres, Redis, MinIO):

```bash
make docker-infra
make migrate
```

### Start the API with hot reload

```bash
cp services/api/.env.example services/api/.env
# Edit .env to match your local setup

make api-dev
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

### With Docker

```bash
make docker-up
```

## Authentication

All endpoints (except `/v1/health`) require an API key in the `X-API-Key` header:

```
X-API-Key: your_tenant_api_key_here
```

Admin endpoints additionally require the admin API key configured in `ADMIN_API_KEY`.

For local development, set a test key in `.env` and use it in requests.

## Key Endpoints

| Endpoint | Description |
|---|---|
| `GET /v1/health` | Service health (no auth required) |
| `GET /v1/races` | List races (filter by date, class, track) |
| `GET /v1/races/{id}/replay` | Commentary replay frames for a race |
| `GET /v1/races/{id}/intelligence` | Full pre-race intelligence package |
| `GET /v1/intelligence/scores/leaderboard` | Top alpha-score runners today |
| `GET /v1/market/steamers` | Today's steaming runners |
| `GET /v1/discovery/patterns` | AI-discovered profitable patterns |
| `GET /v1/tracks/{name}/barrier-analysis` | Gate Advantage Scores |
| `GET /v1/skins/{tenant_slug}` | Tenant skin/brand resolution |
| `GET /v1/search/transcripts` | Search commentary transcripts |

See [docs/api-spec.md](../../docs/api-spec.md) for the complete endpoint reference.

## Adding a New Router

1. Create `app/routers/my_feature.py` with a `router = APIRouter(...)`.
2. Add your endpoints.
3. Import and register in `app/main.py`:
   ```python
   from app.routers import my_feature
   app.include_router(my_feature.router, prefix=PREFIX)
   ```
