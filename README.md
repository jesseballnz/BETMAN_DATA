# BETMAN_DATA

BETMAN_DATA is the BETMAN horse-racing DataOS: a multi-tenant FastAPI + PostgreSQL + Redis platform for racing data, odds intelligence, skinning, compliance, metering, and live delivery, with a React 19 Data Viewer for Demo and Live modes.

## Major capabilities

- **Licensing + tenancy** — isolated tenant keys, scopes, branding, usage metering, and admin controls
- **Security foundations** — hashed API keys, env-driven secrets, readiness checks, security headers, and rate limiting
- **Skin engine** — per-tenant UI branding, feeds, ad slots, and compliance metadata
- **Consumer nerve centre** — ingest race data, odds, feeds, and weather into the warehouse
- **BETMAN intelligence** — market signals, discovery patterns, pedigree, stats, and assistant queries
- **Live delivery** — `/v1/live/{feed_id}` WebSocket fanout backed by Redis pub/sub
- **Observability** — `/v1/health`, `/v1/ready`, `/v1/metrics`, structured request logging, and audit logging
- **Demo-ready webapp** — polished Data Viewer with bundled fixtures, Live/Demo toggle, and resilient fallbacks

## Getting started in 5 minutes

```bash
git clone https://github.com/jesseballnz/BETMAN_DATA.git
cd BETMAN_DATA
cp .env.example .env
# replace every change-me value in .env before starting

make setup

# API
open http://localhost:8000/docs

# Data Viewer
open http://localhost:8080
```

`make setup` copies the root env file if needed, installs Python dependencies, starts Postgres/Redis/MinIO, and applies all migrations.

## Quick start

### Prerequisites

- Python 3.11+
- Node 22+
- Docker + Docker Compose
- `make`

### Local API development

```bash
cp .env.example .env
make install
make docker-infra
make migrate
make api-dev
```

Authentication uses a bearer token in the `Authorization` header. Do **not** send the admin key to the browser; the compose webapp proxy is intended to use a read-only tenant key via `API_PROXY_AUTHORIZATION`.

### Local webapp development

```bash
cd services/webapp
npm install
npm run dev
```

- **Demo** mode uses bundled fixtures and works without the backend.
- **Live** mode uses `VITE_API_BASE_URL` and upgrades to the WebSocket stream when available.

### Required validation commands

```bash
python -m ruff check services/ libs/
python -m pytest tests -q

cd services/webapp
npm run lint
npm run build
```

## Repository layout

```text
BETMAN_DATA/
├── .github/workflows/ci.yml
├── .env.example
├── CONTRIBUTING.md
├── LICENSE
├── Makefile
├── SECURITY.md
├── docker-compose.yml
├── docs/
│   ├── api-spec.md
│   ├── architecture.md
│   ├── betman-scores.md
│   ├── data-model.md
│   ├── deployment.md
│   ├── intelligence-layers.md
│   ├── licensing.md
│   ├── security.md
│   └── use-cases/
│       ├── api-key-metering-billing.md
│       ├── observability-slo.md
│       ├── realtime-websocket.md
│       └── responsible-gambling.md
├── infra/migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_intelligence_layers.sql
│   ├── 003_pedigree_and_providers.sql
│   ├── 004_api_keys_and_security.sql
│   └── README.md
├── libs/
│   └── schemas/
├── services/
│   ├── api/
│   ├── audio-worker/
│   ├── consumer/
│   ├── discovery/
│   ├── ingest/
│   ├── ocr-worker/
│   ├── scoring/
│   └── webapp/
└── tests/
```

## API surface

The FastAPI app currently exposes these router modules under `/v1`:

- `admin`
- `analytics`
- `assistant`
- `compliance`
- `discovery`
- `events`
- `feeds`
- `health`
- `intelligence`
- `live`
- `market`
- `meetings`
- `metrics`
- `pedigree`
- `races`
- `runners`
- `search`
- `skins`
- `stats`
- `tracks`

## Makefile shortcuts

```bash
make setup           # copy env, install deps, start infra, migrate
make install         # install API + consumer + scoring + discovery dev deps
make api-dev         # run FastAPI locally
make consumer-dev    # run consumer locally
make scoring-dev     # run scoring locally
make discovery-dev   # run discovery locally
make docker-infra    # start postgres, redis, minio, minio-init
make docker-up       # start the full stack
make migrate         # apply 001-004
make test            # run all tests
make test-api        # run API tests
make test-consumer   # run consumer tests
make lint            # run ruff
make format          # run ruff format
make security-check  # run ruff + simple secret pattern grep
make status          # show docker status and API health
```

## Documentation

- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [API spec](docs/api-spec.md)
- [Deployment](docs/deployment.md)
- [BETMAN scores](docs/betman-scores.md)
- [Intelligence layers](docs/intelligence-layers.md)
- [Licensing](docs/licensing.md)
- [Security deep dive](docs/security.md)
- [Use case: Responsible gambling](docs/use-cases/responsible-gambling.md)
- [Use case: API key metering and billing](docs/use-cases/api-key-metering-billing.md)
- [Use case: Real-time WebSocket](docs/use-cases/realtime-websocket.md)
- [Use case: Observability and SLOs](docs/use-cases/observability-slo.md)

## Pass 1 highlights

- **Security**: committed secrets removed from compose, hashed tenant key lookup implemented, CORS tightened, security headers and rate limiting added
- **System readiness**: CI workflow added, migrations made re-runnable with tracking, offline API tests expanded, readiness/metrics endpoints added
- **UI/UX**: error boundary, onboarding hint, connection status, accessible Today race controls, and live-mode fallback messaging
- **New use cases**: compliance guardrails, API key metering/billing, authenticated live WebSocket streaming, and observability/SLO foundations
