# BETMAN_DATA

BETMAN_DATA is the data stack for the **BETMAN** platform. It ingests live racing media feeds (Trackside HLS streams), processes audio, video, and images, extracts OCR signals and commentary intelligence, stores structured racing and media metadata in a purpose-built warehouse, and exposes an internal API for querying races, runners, odds, signals, transcripts, clips, and derived events.

---

## Major Capabilities

| Capability | Description |
|---|---|
| **Licensing** | License the platform to any betting or content provider with isolated tenancy and full branding control |
| **Skin Engine** | Multi-tenant branding — per-licensee colors, logos, sponsor slots, ad placements, and custom video/audio feeds |
| **HLS Ingestion** | Consume Trackside 1 and Trackside 2 live HLS streams, segment and store raw media |
| **Consumer Service** | The nerve centre — single gateway for all live data: HLS feeds, race data, odds, and weather |
| **Barrier Analysis** | Track every winner/place-getter's gate across every track, condition, and surface — query "best barrier on a heavy 10 at Ellerslie over 1400m" |
| **Track Science** | WeatherLink API integration — temperature, humidity, multi-probe soil moisture, track conditions — feeds directly into barrier analysis |
| **Odds Intelligence** | Record every odds movement before a race, detect steaming, drifting, and market signals — find the theory in the chaos |
| **Media Storage** | Tiered object storage for raw segments, compressed clips, audio chunks, and keyframes |
| **OCR** | Extract text overlays from video frames — race numbers, runner names, odds, lower-thirds, tote boards |
| **Audio Intelligence** | VAD, commentary vs. ad classification, ASR transcription, race-event detection |
| **Derived Race Signals** | Infer race state events (parade ring, barrier load, jump, result) from audio and visual signals |
| **Warehouse** | Structured PostgreSQL warehouse of racing entities, media metadata, observations, and odds snapshots |
| **Internal API** | FastAPI service exposing races, runners, signals, transcripts, odds, clips, and search |

---

## Repository Layout

```
BETMAN_DATA/
├── README.md                    # This file
├── Makefile                     # Common dev tasks
├── .gitignore
│
├── docs/
│   ├── architecture.md          # Platform architecture overview
│   ├── data-model.md            # Core entity and relationship definitions
│   └── api-spec.md              # Internal API design draft
│
├── services/
│   ├── api/                     # FastAPI internal API service
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── middleware.py    # Tenant auth, request logging, usage tracking
│   │   │   └── routers/
│   │   │       ├── health.py
│   │   │       ├── feeds.py
│   │   │       ├── races.py     # replay, story, excitement, odds-drift, barriers
│   │   │       ├── runners.py
│   │   │       ├── tracks.py    # barrier analysis, heatmap, weather, conditions
│   │   │       ├── events.py
│   │   │       ├── search.py
│   │   │       ├── skins.py     # includes tenant feed resolution
│   │   │       └── admin.py     # tenants, skins, feeds, weather stations, API keys
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── consumer/                # THE NERVE CENTRE — live data gateway
│   │   ├── app/
│   │   │   ├── main.py          # Orchestrates all adapters
│   │   │   ├── config.py
│   │   │   ├── state.py         # Redis-backed live platform state
│   │   │   ├── feed_manager.py  # HLS polling + segment download
│   │   │   ├── race_adapter.py  # External race data feeds
│   │   │   ├── odds_adapter.py  # External odds/pricing feeds
│   │   │   ├── weather_adapter.py # WeatherLink API + soil probes
│   │   │   ├── tenant_router.py # Routes data by tenant feed licensing
│   │   │   └── segment_router.py # Dispatches to processing queues
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── ingest/                  # HLS ingestion worker (placeholder)
│   ├── audio-worker/            # Audio extraction + classification (placeholder)
│   └── ocr-worker/              # Frame extraction + OCR (placeholder)
│
├── libs/                        # Shared internal libraries (placeholder)
│   ├── db/                      # DB session / ORM helpers
│   ├── schemas/                 # Shared Pydantic schemas
│   └── media/                   # Media utility helpers
│
├── infra/
│   └── migrations/              # SQL database migrations
│       └── 001_initial_schema.sql
│
└── tests/                       # Integration and unit tests (placeholder)
```

---

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or Docker)
- `make` (optional but recommended)

### Quick Start

```bash
# Clone the repo
git clone https://github.com/jesseballnz/BETMAN_DATA.git
cd BETMAN_DATA

# Set up the API service
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copy and edit environment config
cp .env.example .env

# Start the API
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. The OpenAPI docs are at `http://localhost:8000/docs`.

### Data Viewer / Webapp

The repository now includes a React + TypeScript + Vite **Data Viewer** at
`services/webapp/`. It provides six tabs for:

- warehouse overview / database sizes
- meetings and races for the day
- market signals
- gates / track heatmaps
- trainer and jockey win-rate boards
- Ask BETMAN natural-language exact search

Run the full stack with:

```bash
docker compose up --build
```

Endpoints:

- API: `http://localhost:8000/v1`
- Data Viewer: `http://localhost:8080`

For standalone frontend development:

```bash
cd services/webapp
npm install
npm run dev
```

Optional frontend env vars:

- `VITE_API_BASE_URL` (defaults to `http://localhost:8000/v1`)
- `VITE_API_BEARER_TOKEN` (only needed when bypassing the nginx proxy)

### Running Migrations

```bash
# Apply migrations against a local Postgres instance
psql $DATABASE_URL -f infra/migrations/001_initial_schema.sql
```

### Makefile Shortcuts

```bash
make api-dev       # Run the API in dev mode
make migrate       # Apply migrations
make test          # Run tests
make lint          # Run ruff linter
make format        # Format code with ruff + black
```

---

## Feeds

| Feed | URL |
|---|---|
| Trackside 1 | `https://trackside-nz.akamaized.net/hls/live/2115595/Trackside1/OnDemand/master.m3u8` |
| Trackside 2 | `https://trackside-nz.akamaized.net/hls/live/2115596/Trackside2/OnDemand/master.m3u8` |

---

## Documentation

- [Architecture](docs/architecture.md)
- [Data Model](docs/data-model.md)
- [API Spec](docs/api-spec.md)
