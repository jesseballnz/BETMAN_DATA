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

A FastAPI service exposing structured racing and signal data.

- Stateless, horizontally scalable.
- Reads from PostgreSQL.
- Does not perform media processing; it is a query layer only.
- Authenticated via shared API key or internal network policy (auth strategy TBD).

See [api-spec.md](api-spec.md) for the endpoint reference.

---

## Technology Choices

| Component | Technology | Rationale |
|---|---|---|
| Ingestion | Python + `m3u8` + `httpx` | Simple, reliable HLS playlist handling |
| Media processing | FFmpeg | Industry standard, broad codec support |
| OCR | Tesseract / PaddleOCR | Practical for overlay text |
| Audio classification | Lightweight CNN or rule-based VAD first | Cost-efficient first pass |
| ASR | Whisper (batch) or streaming ASR | Accurate commentary transcription |
| API | FastAPI | Modern Python, async, OpenAPI built-in |
| Database | PostgreSQL 15+ | Strong JSONB support, full-text search, mature |
| Object storage | S3-compatible | Decoupled from DB, scalable |
| Task queue | Redis + Celery (or ARQ) | Lightweight async task dispatch |
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
      → ocr-worker extracts frames, runs OCR, writes ocr_observations
      → audio-worker extracts audio, runs VAD + classifier, writes audio_events
      → (if commentary) audio-worker runs ASR, writes transcript_segments
  → event prediction pass:
      → reads audio_events + ocr_observations
      → writes race_timeline_events + event_predictions
  → API layer serves:
      → /races/{id}/timeline
      → /races/{id}/signals
      → /search/transcripts
      → /search/ocr
```
