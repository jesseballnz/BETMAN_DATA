# BETMAN_DATA — Platform Architecture

This document describes the intended architecture of the BETMAN_DATA platform. The system is designed to ingest live racing media, extract structured signals, and expose them through an internal API.

---

## Overview

BETMAN_DATA is built in five layers:

```
[Trackside HLS Feeds]
        │
        ▼
[Feed Ingestion Layer]
  - Playlist polling
  - Segment download
  - Keyframe extraction
  - Audio window extraction
        │
        ▼
[Object / Media Storage]
  - Raw HLS segments
  - Compressed clips
  - Audio chunks (AAC/Opus)
  - Keyframe thumbnails
        │
        ▼
[Async Processing Workers]
  - OCR (text overlays, odds, tote boards)
  - Audio classification (VAD, commentary, ad detection)
  - ASR transcription (selective)
  - Scene classification
  - Event prediction
        │
        ▼
[Operational Database + Warehouse]
  - PostgreSQL for metadata and structured observations
  - Racing entities, media refs, signal tables, odds history
        │
        ▼
[BETMAN Data API]
  - FastAPI internal service
  - Query races, signals, odds, clips, transcripts
  - Search OCR text and commentary
```

---

## Layer 1 — Feed Ingestion

**Service:** `services/ingest/`

The ingest workers poll the Trackside 1 and Trackside 2 HLS master playlists at a regular interval. They:

1. Fetch the master playlist and resolve the selected rendition (bitrate, resolution).
2. Fetch the media playlist and identify new segments since the last poll.
3. Download new segments and write them to object storage.
4. Emit a `segment_stored` event to the async task queue.
5. Track segment metadata (duration, sequence number, timestamps) in the `media_segments` table.

**Feeds:**
- Trackside 1: `https://trackside-nz.akamaized.net/hls/live/2115595/Trackside1/OnDemand/master.m3u8`
- Trackside 2: `https://trackside-nz.akamaized.net/hls/live/2115596/Trackside2/OnDemand/master.m3u8`

**Storage conventions:**
- Raw segments: `raw/{feed_id}/{date}/{session_id}/{sequence}.ts`
- Audio chunks: `audio/{feed_id}/{date}/{session_id}/{sequence}.opus`
- Keyframes: `frames/{feed_id}/{date}/{session_id}/{sequence}/{frame_offset}.jpg`

---

## Layer 2 — Object / Media Storage

All media blobs are stored in an S3-compatible object store (e.g. AWS S3, MinIO for local dev). The database records references (`storage_uri`) rather than blobs.

**Tiered retention strategy:**

| Tier | Content | Retention |
|---|---|---|
| Hot | Raw HLS segments | 3–14 days |
| Warm | Compressed clips, audio chunks | 90 days |
| Cold | OCR frames, thumbnails | 1 year |
| Permanent | Derived signals, transcripts, event metadata | Indefinite |

**Smart clipping:** Rather than retaining all raw video equally, the system identifies high-value windows (pre-start build-up, barrier loading, jump, live race call, result announcement) and preserves those as compressed clips. Low-value windows (ads, silence, idle cameras) are discarded or archived at low priority.

---

## The Vision

BETMAN_DATA is not just a data warehouse — it is an intelligence platform built around live racing. The goal is to make every race **replayable, searchable, and understandable** from its audio and visual signals alone. A new engineer or product team should be able to query "show me the last 30 seconds of commentary before Rocket Man crossed the line in the 2024 Auckland Cup" and get back structured, timestamped, visually-rich data immediately.

Every design decision is made with two questions in mind:
1. Can a front-end consume this without further transformation?
2. Can a data scientist train a model on this tomorrow?

---

## Layer 3 — Async Processing Workers

Workers consume events from the task queue and operate on stored segments.

### `services/ocr-worker/`

1. Receive a `segment_stored` event.
2. Extract keyframes at a configured interval (e.g. every 2 seconds).
3. Run OCR over each frame.
4. Classify detected text regions (race number, runner name, odds, tote, lower-third, clock).
5. Write `ocr_observations` records.

### `services/audio-worker/`

1. Receive a `segment_stored` event.
2. Demux audio from the segment using FFmpeg.
3. Run Voice Activity Detection (VAD) to find speech windows.
4. Classify each speech window: `commentary`, `advertisement`, `parade_ring`, `pre_start_build`, `race_call`, `result_read`, `ambient`.
5. For windows classified as race commentary, optionally run ASR (Whisper-class or streaming ASR).
6. Write `audio_events` and `transcript_segments` records.

**Cost control:**
- Only transcribe windows with high speech + sports-commentary probability.
- Sample low-information periods sparsely.
- Run heavier ML models only on shortlisted windows.
- Allow offline reprocessing of archived audio later.

### Event prediction

A separate pass over `audio_events` and `ocr_observations` generates `event_predictions` and `race_timeline_events`, e.g.:
- `parade_ring_started`
- `barriers_loading`
- `jump_imminent`
- `race_live`
- `finish_detected`
- `result_announced`

### Event prediction

A separate pass over `audio_events` and `ocr_observations` generates `event_predictions` and `race_timeline_events`, e.g.:
- `parade_ring_started`
- `barriers_loading`
- `jump_imminent`
- `race_live`
- `finish_detected`
- `result_announced`

---

## Layer 3b — Intelligence Layer

This is where BETMAN_DATA moves from a data store to a platform. After raw signals are extracted, a second pass of intelligence workers enriches the data.

### Scene Classification

Every keyframe is classified into one of: `studio`, `parade_ring`, `mounting_yard`, `barriers`, `live_race`, `finish`, `replay`, `advertisement`, `interview`. This powers the visual timeline and smart clipping, and lets the API filter media by scene type. Stored in `scene_classifications`.

### Excitement Scoring

Each audio window is scored for excitement level (0–1) using a lightweight audio model trained to distinguish the flat tone of a pre-race parade from the crescendo of a finish call. Excitement scores are stored per window and exposed as a time-series chart endpoint (`GET /races/{id}/excitement`). This is the spine of the replay visualization.

### Commentary Named Entity Recognition (NER)

After ASR transcription, an NER pass extracts structured data from commentary text:
- **Runner positions** — "Rocket Man leads from Thunder Ridge at the 600" → `[{position: 1, runner: "Rocket Man"}, {position: 2, runner: "Thunder Ridge"}]`
- **Distance calls** — "at the 800 metre mark"
- **Runner mentions** — any runner name reference
- **Race signals** — "they're racing", "and he wins", "protest flag is up"

Stored in `commentary_entities`, linked to `transcript_segments`. This is what makes commentary replay rich — the system knows *who* is being talked about at every moment.

### Race Story Generation

After a race completes, an LLM pass synthesises the transcript segments, race timeline events, and key commentary entities into a concise, engaging narrative stored in `race_summaries`. Example output:

> *"In a dramatic running of the 2024 Auckland Cup, Rocket Man (barrier 5) surged from midfield at the 600m mark to overhaul Thunder Ridge in the final strides. The crowd's excitement peaked at the 200m as the two leaders drew clear of the field. Rocket Man's winning margin was a head in a race run in 3:18.2."*

This narrative is served directly by `GET /races/{id}/story`.

### Vector Embeddings

For each race, runner, and significant audio window, we generate vector embeddings. These enable:
- **Similarity search** — "find races with a finish like this one"
- **Runner recognition** — match a visual crop to a known runner
- **Commentary pattern detection** — find races where the commentary structure matched "dominated wire-to-wire"

Stored in `runner_embeddings` using [pgvector](https://github.com/pgvector/pgvector).

---

## Layer 4 — Operational Database + Warehouse

**Database:** PostgreSQL 15+

The schema is split into logical domains:

- **Racing entities** — `meetings`, `races`, `runners`, `race_entries`, `race_classes`
- **Feed / media** — `feeds`, `stream_sessions`, `media_segments`, `audio_chunks`, `keyframes`, `clips`
- **Signals / observations** — `ocr_observations`, `audio_events`, `transcript_segments`, `event_predictions`, `odds_snapshots`, `race_timeline_events`

See [data-model.md](data-model.md) for the full entity reference.

**Future analytical layer:** For heavy analytics (time-series aggregations, large scan queries), the system may introduce DuckDB or ClickHouse as a read replica for analytical workloads, leaving PostgreSQL as the operational source of truth.

---

## Layer 5 — BETMAN Data API

**Service:** `services/api/`

A FastAPI service exposing structured racing and signal data. Designed to be consumed directly by front-ends and internal tooling without further transformation — every response includes the data needed to render a rich visual experience.

**Visualization-first design principles:**
- Replay endpoints return time-ordered frames ready to step through
- Odds endpoints return chart-ready time-series arrays
- Timeline endpoints include thumbnail URLs alongside every event
- All timestamps include both UTC ISO-8601 and a `offset_ms` relative to race start
- Excitement scores are included on any time-indexed resource

**Real-time capabilities:**
- `WS /live/{feed_id}` — WebSocket stream of live race events as they are detected
- Clients receive structured JSON events: commentary fragments, excitement spikes, position calls, odds updates, race state transitions

See [api-spec.md](api-spec.md) for the full endpoint reference.

---

## Layer 6 — Skin Engine (Multi-Tenant Licensing)

BETMAN_DATA is designed to be licensed to external betting operators and content providers — Racing.com, Ladbrokes, William Hill, and others. Each licensee gets a fully branded experience without any change to the underlying data platform.

### Tenants

Each licensee is a **tenant** in the system. A tenant has:
- A unique `slug` used in API paths and asset namespacing
- A license type (`full`, `content_only`, `odds_only`)
- A license expiry date
- One or more **skins**

### Skins

A **skin** is a named, versioned branding configuration owned by a tenant. It defines:
- **Colors** — primary, secondary, accent, background, text
- **Typography** — font family, heading weight
- **Logos and assets** — main logo, dark-mode logo, favicon, sponsor watermarks
- **Feature flags** — which platform features the tenant's users can access (commentary replay, race stories, similarity search, etc.)
- **Layout options** — replay overlay style, excitement bar style, card layout

A single tenant can have multiple skins (e.g., "Ladbrokes Dark", "Ladbrokes Light", "Ladbrokes G1 Premium"). Skins can be scoped by context — a tenant may show one skin for standard races and a premium-branded skin for Group 1 events.

### Skin Contexts

Skin selection is hierarchical and resolved at request time:

```
global tenant skin
  → race class skin (e.g., all G1 races use the premium skin)
    → meeting skin (e.g., Melbourne Cup carnival branding)
      → race skin (e.g., a specific sponsored race)
```

The highest-priority matching context wins.

### Advertising Slots

The skin engine includes a structured ad slot system. **Ad slot types** define named positions within the UI (e.g., `replay_overlay_top`, `pre_race_banner`, `results_sidebar`, `race_card_footer`). Each slot has defined dimensions and a display context.

**Ad placements** assign a creative asset to a slot for a skin within an active time window. The API resolves the active ad for any slot at query time.

### Admin Interface

The admin API (`/admin/`) provides full CRUD for:
- Tenants (create, update, activate/deactivate)
- Skins (create, configure, set as default)
- Skin assets (upload logos, backgrounds, sponsor creatives)
- Ad placements (assign ads to slots, set active windows)
- Skin contexts (scope a skin to a race class, meeting, or race)

This is the interface used by operators to set up a new licensee and configure their brand.

### Skin Resolution (Public API)

Front-ends resolve the active skin for a given context via:
```
GET /skins/{tenant_slug}?race_class=G1&meeting_id=42
```

This returns the fully resolved skin config — colors, logo URLs, feature flags, and active ad placements — ready to apply directly to a front-end renderer.

---

## Summary Architecture Diagram

```
[Trackside HLS Feeds]
        │
        ▼
[Feed Ingestion]  ──→  [Object Storage]
        │
        ▼
[Async Processing]
  OCR · Audio · Scene Classification · Excitement Scoring · NER
        │
        ▼
[Intelligence Layer]
  Race Stories · Vector Embeddings · Event Predictions
        │
        ▼
[PostgreSQL + pgvector]
  Racing · Media · Signals · Odds · Skin Engine
        │
        ▼
[BETMAN Data API  ·  Admin API  ·  WebSocket Live Stream]
        │
        ▼
[Licensee Front-Ends — branded via Skin Engine]
  Racing.com  ·  Ladbrokes  ·  William Hill  ·  ...
```

| Component | Technology | Rationale |
|---|---|---|
| Ingestion | Python + `m3u8` + `httpx` | Simple, reliable HLS playlist handling |
| Media processing | FFmpeg | Industry standard, broad codec support |
| OCR | PaddleOCR / Tesseract | Practical for overlay text |
| Scene classification | EfficientNet / lightweight CNN | Fast inference per frame |
| Audio classification | Lightweight CNN or rule-based VAD first | Cost-efficient first pass |
| Excitement scoring | Audio feature model (RMS, spectral centroid) | Real-time capable |
| ASR | Whisper (batch) or streaming ASR | Accurate commentary transcription |
| NER | spaCy + custom racing entity model | Runner/position extraction |
| Race story generation | OpenAI / local LLM (post-race batch) | Rich narrative summaries |
| Vector embeddings | pgvector extension on PostgreSQL | Similarity search without extra infra |
| API | FastAPI | Modern Python, async, OpenAPI built-in |
| Real-time | FastAPI WebSocket | Low-latency live event stream |
| Database | PostgreSQL 15+ with pgvector | Strong JSONB, full-text search, vectors |
| Object storage | S3-compatible | Decoupled from DB, scalable |
| Task queue | Redis + ARQ or Celery | Lightweight async task dispatch |
| Local dev | Docker Compose | Simple local environment parity |

---

## Expected Data Flow (End-to-End)

```
Trackside HLS stream
  → ingest worker polls playlist
  → downloads .ts segment
  → writes to object storage
  → inserts media_segments record
  → emits segment_stored event
      → ocr-worker:
          extracts keyframes
          classifies scene → scene_classifications
          runs OCR → ocr_observations
      → audio-worker:
          extracts audio window
          runs VAD + classifier → audio_events
          scores excitement → excitement_scores
          (if commentary) runs ASR → transcript_segments
          runs NER → commentary_entities
      → event prediction pass:
          reads audio_events + ocr_observations
          writes race_timeline_events + event_predictions
      → (post-race) intelligence pass:
          generates race_summaries (LLM)
          generates runner_embeddings (vector model)
  → API layer serves:
      → GET /races/{id}/replay     ← time-ordered commentary + events
      → GET /races/{id}/story      ← AI narrative
      → GET /races/{id}/excitement ← chart-ready excitement time-series
      → GET /races/{id}/odds-drift ← chart-ready odds time-series
      → GET /races/{id}/scene-timeline ← visual scene breakdown with thumbnails
      → GET /search/similar        ← embedding-based race similarity
      → WS /live/{feed_id}         ← real-time event stream
```
