# BETMAN_DATA

BETMAN_DATA is the data stack for the **BETMAN** platform. It ingests live racing media feeds (Trackside HLS streams), processes audio, video, and images, extracts OCR signals and commentary intelligence, stores structured racing and media metadata in a purpose-built warehouse, and exposes an internal API for querying races, runners, odds, signals, transcripts, clips, and derived events.

---

## Major Capabilities

| Capability | Description |
|---|---|
| **Licensing** | License the platform to any betting or content provider with isolated tenancy and full branding control |
| **Skin Engine** | Multi-tenant branding — per-licensee colors, logos, sponsor slots, and ad placements with an admin interface |
| **HLS Ingestion** | Consume Trackside 1 and Trackside 2 live HLS streams, segment and store raw media |
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
│   │   │   ├── main.py          # App entrypoint
│   │   │   ├── config.py        # Settings / environment config
│   │   │   └── routers/
│   │   │       ├── __init__.py
│   │   │       ├── health.py
│   │   │       ├── feeds.py
│   │   │       ├── races.py     # includes /replay, /story, /excitement, /odds-drift
│   │   │       ├── runners.py
│   │   │       ├── events.py
│   │   │       ├── search.py    # OCR, transcript, similarity search
│   │   │       ├── skins.py     # Public skin resolution for licensees
│   │   │       └── admin.py     # Admin: tenants, skins, assets, ad slots
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── ingest/                  # HLS ingestion worker (placeholder)
│   ├── audio-worker/            # Audio extraction + classification worker (placeholder)
│   └── ocr-worker/              # Frame extraction + OCR worker (placeholder)
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
