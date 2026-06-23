# BETMAN_DATA — Data Model

This document describes the core entities, relationships, and design decisions for the BETMAN_DATA warehouse.

---

## Entity Domains

The schema is organised into four domains:

1. **Racing** — the canonical racing entities
2. **Feed / Media** — raw and derived media assets
3. **Signals / Observations** — extracted data from media (OCR, audio, events)
4. **Market / Odds** — odds and pricing snapshots

---

## Domain 1 — Racing Entities

### `race_classes`

Normalises race class codes into a structured hierarchy. This table is the source of truth for filtering by class.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `code` | `text UNIQUE NOT NULL` | Display code: `G1`, `G2`, `G3`, `L`, `R75`, `MDN`, `BM65`, etc. |
| `group` | `text NOT NULL` | Normalised group: `group`, `listed`, `rating_band`, `benchmark`, `maiden`, `open`, `age_restricted` |
| `rank` | `integer` | Sortable hierarchy — lower = more prestigious |
| `description` | `text` | Human-readable label |

**Race class normalisation examples:**

| Code | Group | Rank | Description |
|---|---|---|---|
| `G1` | `group` | 1 | Group 1 |
| `G2` | `group` | 2 | Group 2 |
| `G3` | `group` | 3 | Group 3 |
| `L` | `listed` | 4 | Listed |
| `R75` | `rating_band` | 50 | Rating 75+ handicap |
| `BM65` | `benchmark` | 60 | Benchmark 65 |
| `MDN` | `maiden` | 90 | Maiden |
| `2YO` | `age_restricted` | 80 | Two-year-olds only |

This design allows:
- Exact filtering by code (`race_class_code = 'G1'`)
- Group filtering (`race_class_group = 'group'`)
- Ranked ordering (`ORDER BY race_class_rank`)

---

### `meetings`

A race meeting at a specific track on a specific day.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `external_meeting_id` | `text` | Source system ID |
| `track_name` | `text NOT NULL` | e.g. `Ellerslie`, `Trentham` |
| `meeting_date` | `date NOT NULL` | |
| `surface` | `text` | `turf`, `synthetic`, `harness`, `greyhound` |
| `jurisdiction` | `text` | `NZ`, `AU`, etc. |
| `status` | `text` | `scheduled`, `abandoned`, `completed` |
| `created_at` | `timestamptz` | |

---

### `races`

An individual race within a meeting.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `meeting_id` | `integer FK → meetings` | |
| `external_race_id` | `text` | Source system ID |
| `race_number` | `integer NOT NULL` | Race number on the card |
| `name` | `text` | Race name |
| `distance_m` | `integer` | Distance in metres |
| `scheduled_start_time` | `timestamptz` | |
| `actual_start_time` | `timestamptz` | Populated when confirmed |
| `race_class_id` | `integer FK → race_classes` | |
| `race_class_code` | `text` | Denormalised for fast filtering |
| `prize_money` | `numeric` | |
| `surface` | `text` | Override if differs from meeting |
| `status` | `text` | `scheduled`, `running`, `finished`, `abandoned` |
| `created_at` | `timestamptz` | |

---

### `runners`

Individual horses, dogs, or harness drivers.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `external_runner_id` | `text` | Source system ID |
| `name` | `text NOT NULL` | Runner name |
| `type` | `text` | `thoroughbred`, `harness`, `greyhound` |
| `country_of_origin` | `text` | |
| `created_at` | `timestamptz` | |

---

### `race_entries`

Links runners to races (the race card / field).

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `race_id` | `integer FK → races` | |
| `runner_id` | `integer FK → runners` | |
| `barrier_number` | `integer` | |
| `saddle_cloth` | `text` | Display number |
| `jockey_or_driver` | `text` | |
| `trainer` | `text` | |
| `weight_kg` | `numeric` | |
| `scratched` | `boolean DEFAULT false` | |
| `final_position` | `integer` | Populated post-race |
| `created_at` | `timestamptz` | |

---

## Domain 2 — Feed / Media Entities

### `feeds`

Represents a named live media feed source.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `name` | `text NOT NULL` | e.g. `Trackside 1`, `Trackside 2` |
| `url` | `text NOT NULL` | HLS master playlist URL |
| `active` | `boolean DEFAULT true` | |
| `created_at` | `timestamptz` | |

---

### `stream_sessions`

A continuous ingestion session for a feed (one session per startup).

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `feed_id` | `integer FK → feeds` | |
| `started_at` | `timestamptz NOT NULL` | |
| `ended_at` | `timestamptz` | Null if still active |
| `status` | `text` | `active`, `ended`, `error` |
| `selected_rendition_url` | `text` | The chosen HLS variant URL |
| `created_at` | `timestamptz` | |

---

### `media_segments`

Individual HLS `.ts` segments downloaded from a stream.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `feed_id` | `integer FK → feeds` | |
| `stream_session_id` | `integer FK → stream_sessions` | |
| `sequence_number` | `bigint NOT NULL` | HLS media sequence |
| `segment_started_at` | `timestamptz NOT NULL` | Wall-clock start time |
| `segment_ended_at` | `timestamptz NOT NULL` | Wall-clock end time |
| `duration_ms` | `integer NOT NULL` | Segment duration in milliseconds |
| `storage_uri` | `text NOT NULL` | Object storage path |
| `content_hash` | `text` | SHA-256 of raw bytes |
| `codec` | `text` | e.g. `h264` |
| `resolution` | `text` | e.g. `1920x1080` |
| `bitrate` | `integer` | Bits per second |
| `audio_codec` | `text` | e.g. `aac` |
| `processing_status` | `text DEFAULT 'pending'` | `pending`, `processing`, `done`, `error` |
| `created_at` | `timestamptz` | |

---

### `audio_chunks`

Extracted audio windows from segments (may span multiple segments).

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `segment_id` | `integer FK → media_segments` | |
| `started_at` | `timestamptz NOT NULL` | |
| `ended_at` | `timestamptz NOT NULL` | |
| `duration_ms` | `integer NOT NULL` | |
| `storage_uri` | `text NOT NULL` | |
| `codec` | `text` | e.g. `opus`, `aac` |
| `sample_rate` | `integer` | Hz |
| `created_at` | `timestamptz` | |

---

### `keyframes`

Individual extracted frames from segments.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `segment_id` | `integer FK → media_segments` | |
| `frame_timestamp` | `timestamptz NOT NULL` | Exact time of frame |
| `offset_ms` | `integer NOT NULL` | Offset within segment |
| `storage_uri` | `text NOT NULL` | |
| `width` | `integer` | |
| `height` | `integer` | |
| `created_at` | `timestamptz` | |

---

### `clips`

Derived compressed video clips around high-value events.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `feed_id` | `integer FK → feeds` | |
| `race_id` | `integer FK → races` | Nullable |
| `clip_type` | `text` | `pre_start`, `barrier_load`, `race_live`, `finish`, `result`, `highlight` |
| `started_at` | `timestamptz NOT NULL` | |
| `ended_at` | `timestamptz NOT NULL` | |
| `duration_ms` | `integer NOT NULL` | |
| `storage_uri` | `text NOT NULL` | |
| `codec` | `text` | |
| `resolution` | `text` | |
| `created_at` | `timestamptz` | |

---

## Domain 3 — Signal / Observation Entities

### `ocr_observations`

Text extracted from video frames via OCR.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `segment_id` | `integer FK → media_segments` | |
| `keyframe_id` | `integer FK → keyframes` | Nullable |
| `frame_timestamp` | `timestamptz NOT NULL` | |
| `detected_text` | `text NOT NULL` | Raw OCR output |
| `normalized_text` | `text` | Cleaned/normalised version |
| `observation_type` | `text` | `race_number`, `runner_name`, `odds`, `clock`, `lower_third`, `tote`, `unknown` |
| `confidence` | `real` | 0–1 |
| `bbox_json` | `jsonb` | Bounding box `{x, y, w, h}` |
| `created_at` | `timestamptz` | |

---

### `audio_events`

Classified audio windows from the audio worker.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `segment_id` | `integer FK → media_segments` | |
| `audio_chunk_id` | `integer FK → audio_chunks` | Nullable |
| `started_at` | `timestamptz NOT NULL` | |
| `ended_at` | `timestamptz NOT NULL` | |
| `event_type` | `text NOT NULL` | `commentary`, `advertisement`, `parade_ring`, `pre_start_build`, `race_call`, `result_read`, `ambient`, `silence`, `unknown` |
| `confidence` | `real` | 0–1 |
| `model_version` | `text` | Model/version used |
| `created_at` | `timestamptz` | |

---

### `transcript_segments`

ASR-transcribed speech from classified commentary windows.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `audio_event_id` | `integer FK → audio_events` | |
| `started_at` | `timestamptz NOT NULL` | |
| `ended_at` | `timestamptz NOT NULL` | |
| `text` | `text NOT NULL` | Transcribed text |
| `language` | `text DEFAULT 'en'` | |
| `confidence` | `real` | |
| `model_version` | `text` | |
| `created_at` | `timestamptz` | |

---

### `event_predictions`

Model-derived predictions about race state, based on audio and visual signals.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `race_id` | `integer FK → races` | Nullable — may not yet be linked |
| `feed_id` | `integer FK → feeds` | |
| `event_type` | `text NOT NULL` | `parade_ring_started`, `barriers_loading`, `jump_imminent`, `race_live`, `finish_detected`, `result_announced` |
| `predicted_at` | `timestamptz NOT NULL` | Wall-clock time of prediction |
| `confidence` | `real` | |
| `source_type` | `text` | `audio`, `ocr`, `combined` |
| `source_ids` | `integer[]` | IDs of contributing observations |
| `payload_json` | `jsonb` | Additional context |
| `created_at` | `timestamptz` | |

---

### `race_timeline_events`

Canonical, resolved timeline events for a race (derived from predictions and confirmed signals).

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `race_id` | `integer FK → races NOT NULL` | |
| `event_type` | `text NOT NULL` | `scheduled_start`, `actual_start`, `finish`, `result_official`, `abandoned`, `scratching` |
| `event_time` | `timestamptz NOT NULL` | |
| `source_type` | `text` | `feed_data`, `ocr`, `audio`, `manual` |
| `source_id` | `integer` | FK to source table |
| `confidence` | `real` | |
| `payload_json` | `jsonb` | |
| `created_at` | `timestamptz` | |

---

### `odds_snapshots`

Point-in-time odds captured for each runner.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `race_id` | `integer FK → races NOT NULL` | |
| `race_entry_id` | `integer FK → race_entries` | |
| `captured_at` | `timestamptz NOT NULL` | |
| `source` | `text NOT NULL` | `ocr_tote`, `api_feed`, `manual` |
| `win_price` | `numeric` | |
| `place_price` | `numeric` | |
| `win_sp` | `numeric` | Starting price win |
| `place_sp` | `numeric` | Starting price place |
| `market_status` | `text` | `open`, `suspended`, `closed` |
| `created_at` | `timestamptz` | |

---

## Domain 4 — Intelligence Entities

### `scene_classifications`

ML-classified scene type for each keyframe.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `keyframe_id` | `integer FK → keyframes NOT NULL` | |
| `scene_type` | `text NOT NULL` | `studio`, `parade_ring`, `mounting_yard`, `barriers`, `live_race`, `finish`, `replay`, `advertisement`, `interview` |
| `confidence` | `real` | 0–1 |
| `model_version` | `text` | |
| `created_at` | `timestamptz` | |

---

### `excitement_scores`

Audio excitement level scored per window. Used to drive replay visualisations and highlight detection.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `audio_event_id` | `integer FK → audio_events NOT NULL` | |
| `race_id` | `integer FK → races` | Nullable — resolved after entity matching |
| `race_offset_ms` | `integer` | Milliseconds from actual race start (negative = pre-race) |
| `score` | `real NOT NULL` | 0–1 excitement level |
| `peak` | `boolean DEFAULT false` | True if this is a local excitement peak |
| `model_version` | `text` | |
| `created_at` | `timestamptz` | |

---

### `commentary_entities`

Named entities extracted from transcript segments via NER. The key table for powering commentary replay with structured position data.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `transcript_segment_id` | `integer FK → transcript_segments NOT NULL` | |
| `entity_type` | `text NOT NULL` | `runner_name`, `position_call`, `distance_call`, `race_signal`, `jockey_name` |
| `raw_text` | `text NOT NULL` | Extracted text span |
| `normalized_value` | `text` | e.g. `Rocket Man` (cleaned), `1` (for position), `600` (distance in metres) |
| `runner_id` | `integer FK → runners` | Resolved if entity_type = `runner_name` |
| `position` | `integer` | Resolved race position if entity_type = `position_call` |
| `confidence` | `real` | |
| `created_at` | `timestamptz` | |

**Example NER output for** *"Rocket Man leads from Thunder Ridge at the 600"*:
```
{entity_type: "runner_name",   raw_text: "Rocket Man",    position: 1}
{entity_type: "runner_name",   raw_text: "Thunder Ridge",  position: 2}
{entity_type: "distance_call", raw_text: "the 600",        normalized_value: "600"}
{entity_type: "position_call", raw_text: "leads from",     position: 1}
```

---

### `race_summaries`

AI-generated narrative summaries produced after a race completes.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `race_id` | `integer FK → races UNIQUE NOT NULL` | One summary per race |
| `summary_text` | `text NOT NULL` | Full narrative |
| `key_moments` | `jsonb` | Array of `{offset_ms, text, type}` highlight moments |
| `winner_name` | `text` | Extracted winner |
| `margin_description` | `text` | e.g. `"a head"`, `"two lengths"` |
| `model_version` | `text` | LLM model/version used |
| `generated_at` | `timestamptz NOT NULL` | |
| `created_at` | `timestamptz` | |

---

### `runner_embeddings`

Vector embeddings for runners and races, enabling similarity search. Requires the `pgvector` PostgreSQL extension.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `subject_type` | `text NOT NULL` | `runner`, `race`, `audio_window` |
| `subject_id` | `integer NOT NULL` | FK to the appropriate table |
| `embedding_type` | `text NOT NULL` | `visual`, `audio`, `commentary`, `combined` |
| `embedding` | `vector(1536)` | pgvector column |
| `model_version` | `text` | |
| `created_at` | `timestamptz` | |

---

### Updated: `transcript_segments`

> **Addition for commentary replay:** `race_id` and `race_offset_ms` are added to link transcripts directly to their race and position on the race timeline. This is the foundation of the `GET /races/{id}/replay` endpoint.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `audio_event_id` | `integer FK → audio_events` | |
| `race_id` | `integer FK → races` | Resolved race (nullable until matched) |
| `race_offset_ms` | `integer` | Milliseconds from `races.actual_start_time` (negative = pre-race) |
| `started_at` | `timestamptz NOT NULL` | |
| `ended_at` | `timestamptz NOT NULL` | |
| `text` | `text NOT NULL` | Transcribed text |
| `language` | `text DEFAULT 'en'` | |
| `confidence` | `real` | |
| `model_version` | `text` | |
| `created_at` | `timestamptz` | |

---

## Domain 5 — Skin Engine

The skin engine enables BETMAN_DATA to be licensed to external betting operators and content providers. Each licensee (tenant) gets fully isolated branding, configurable through an admin API.

### `tenants`

A licensed operator or content provider.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `name` | `text NOT NULL` | e.g. `Ladbrokes`, `Racing.com`, `William Hill` |
| `slug` | `text UNIQUE NOT NULL` | URL-safe key: `ladbrokes`, `racing-com` |
| `contact_email` | `text` | |
| `license_type` | `text NOT NULL` | `full`, `content_only`, `odds_only` |
| `license_expires_at` | `timestamptz` | |
| `active` | `boolean DEFAULT true` | |
| `created_at` | `timestamptz` | |

---

### `skins`

A named branding configuration for a tenant.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `tenant_id` | `integer FK → tenants NOT NULL` | |
| `name` | `text NOT NULL` | e.g. `Ladbrokes Dark`, `G1 Premium` |
| `slug` | `text NOT NULL` | e.g. `ladbrokes-dark` |
| `is_default` | `boolean DEFAULT false` | Default skin for this tenant |
| `active` | `boolean DEFAULT true` | |
| `config_json` | `jsonb NOT NULL DEFAULT '{}'` | Colors, typography, layout, feature flags |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | |

**`config_json` schema:**
```json
{
  "colors": {
    "primary": "#e63329",
    "secondary": "#1a1a2e",
    "accent": "#f5a623",
    "text": "#ffffff",
    "background": "#0d0d0d"
  },
  "typography": {
    "font_family": "Inter, sans-serif",
    "heading_weight": "700"
  },
  "layout": {
    "replay_overlay_style": "cinematic",
    "excitement_bar_style": "gradient",
    "show_sponsor_watermark": true
  },
  "features": {
    "commentary_replay": true,
    "race_story": true,
    "similarity_search": false,
    "live_websocket": true,
    "show_odds": true
  }
}
```

---

### `skin_contexts`

Scopes a skin to a specific context. Multiple contexts can match; the highest priority wins.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `skin_id` | `integer FK → skins NOT NULL` | |
| `context_type` | `text NOT NULL` | `global`, `race_class`, `meeting`, `race`, `event` |
| `context_ref` | `text` | e.g. `G1` for `race_class`, race ID for `race` |
| `priority` | `integer DEFAULT 0` | Higher wins when multiple contexts match |
| `created_at` | `timestamptz` | |

---

### `skin_assets`

Uploaded brand assets associated with a skin (logos, backgrounds, sponsor creatives).

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `skin_id` | `integer FK → skins NOT NULL` | |
| `asset_type` | `text NOT NULL` | `logo`, `logo_dark`, `favicon`, `background`, `sponsor_logo`, `watermark`, `ad_creative` |
| `label` | `text` | Human-readable label |
| `storage_uri` | `text NOT NULL` | Object storage path |
| `cdn_url` | `text` | Resolved public CDN URL |
| `file_format` | `text` | `png`, `svg`, `webp`, `jpg` |
| `width` | `integer` | Pixels |
| `height` | `integer` | Pixels |
| `created_at` | `timestamptz` | |

---

### `ad_slot_types`

Defines named advertising positions available within the platform UI.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `code` | `text UNIQUE NOT NULL` | `replay_overlay_top`, `pre_race_banner`, `results_sidebar`, `race_card_footer`, `commentary_interstitial` |
| `description` | `text` | |
| `dimensions` | `text` | e.g. `728x90`, `300x250` |
| `display_context` | `text` | `replay`, `pre_race`, `results`, `race_card`, `live` |

---

### `ad_placements`

An ad creative assigned to a slot within a skin for a time window.

| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `skin_id` | `integer FK → skins NOT NULL` | |
| `slot_type_id` | `integer FK → ad_slot_types NOT NULL` | |
| `asset_id` | `integer FK → skin_assets` | The ad creative |
| `label` | `text` | |
| `click_url` | `text` | Destination URL |
| `active_from` | `timestamptz` | |
| `active_until` | `timestamptz` | |
| `priority` | `integer DEFAULT 0` | Fallback ordering |
| `created_at` | `timestamptz` | |

---

## Updated Key Relationships

```
tenants ──< skins ──< skin_contexts
                  ──< skin_assets
                  ──< ad_placements >── ad_slot_types
                                    >── skin_assets (creative)

races ──< race_timeline_events
      ──< odds_snapshots
      ──< event_predictions
      ──  race_summaries (1:1)

transcript_segments ──< commentary_entities
audio_events ──< excitement_scores
keyframes ──< scene_classifications

runner_embeddings (subject_type=runner) >── runners
runner_embeddings (subject_type=race)   >── races
```

```
meetings ──< races ──< race_entries >── runners
                │
                └──< race_timeline_events
                └──< odds_snapshots
                └──< event_predictions

feeds ──< stream_sessions ──< media_segments ──< audio_chunks
                                             ──< keyframes
                                             ──< ocr_observations
                                             ──< audio_events ──< transcript_segments

media_segments ──< clips
races ──< clips
```

---

## Design Notes

- **Race class filtering** is a first-class concern. Use `race_class_code` for exact matches and `race_classes.group` for category-level filtering.
- **Timestamps** are always stored as `timestamptz` (UTC). The application layer is responsible for converting to local time for display.
- **`storage_uri`** fields contain a relative object-store path (`raw/feed_1/2024-01-15/session_42/0001.ts`). The base URL is resolved at query time from environment config.
- **`payload_json`** and `bbox_json` fields use JSONB for flexible storage of structured extension data without requiring schema migrations for every new attribute.
- Indexes on `race_id`, `feed_id`, `segment_started_at`, and `frame_timestamp` columns will be critical for query performance at scale.
