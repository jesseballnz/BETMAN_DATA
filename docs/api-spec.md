# BETMAN_DATA — Internal API Specification

This document describes the BETMAN_DATA internal API. The API is designed to be consumed directly by front-ends and internal tooling — every response is structured for immediate visual rendering without further transformation.

**Base URL:** `https://data-api.betman.internal/v1`  
**Protocol:** HTTPS + WebSocket  
**Format:** JSON (application/json)  
**Auth:** ****** (API key per tenant, passed as `Authorization: ******

---

## Design Principles

- **Visualization-first** — every time-indexed resource includes `offset_ms` (milliseconds from race start), `excitement_score`, and where applicable a `thumbnail_url`
- **Flat and complete** — responses include the data needed to render without additional requests
- **Skin-aware** — tenant front-ends resolve their branding config once via `/skins/{tenant}`, then apply it client-side
- **Consistent errors** — all errors follow `{"error": "code", "message": "...", "detail": {...}}`

---

## 1. Health

### `GET /health`

Liveness and readiness check.

**Response `200`:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2024-03-09T03:00:00Z"
}
```

---

## 2. Feeds

### `GET /feeds`

List all configured live media feeds.

**Response `200`:**
```json
{
  "feeds": [
    {
      "id": 1,
      "name": "Trackside 1",
      "url": "https://trackside-nz.akamaized.net/hls/live/2115595/Trackside1/OnDemand/master.m3u8",
      "active": true,
      "current_session_id": 88
    },
    {
      "id": 2,
      "name": "Trackside 2",
      "url": "https://trackside-nz.akamaized.net/hls/live/2115596/Trackside2/OnDemand/master.m3u8",
      "active": true,
      "current_session_id": 89
    }
  ]
}
```

### `GET /feeds/{id}`

Get a single feed with recent session info.

---

## 2.5 Stats

### `GET /stats/overview`

Warehouse-level KPI payload for the Data Viewer overview tab.

Returns:

- total database size
- per-table approximate row counts and storage sizes
- key entity counts (meetings, races, runners, entries, odds snapshots)
- freshness markers (`latest_odds_snapshot`, `latest_weather_reading`, `latest_media_segment`, `latest_meeting_date`)
- 24h ingestion counts for high-volume tables

---

## 3. Races

### `GET /races`

List races with optional filtering.

**Query parameters:**

| Param | Type | Description |
|---|---|---|
| `date` | `YYYY-MM-DD` | Filter by meeting date |
| `track` | `string` | Filter by track name |
| `race_class` | `string` | Exact class code: `G1`, `R75`, `MDN`, etc. |
| `race_class_group` | `string` | Group: `group`, `listed`, `rating_band`, `maiden` |
| `status` | `string` | `scheduled`, `running`, `finished` |
| `limit` | `integer` | Max results (default 50) |
| `offset` | `integer` | Pagination offset |

**Response `200`:**
```json
{
  "races": [
    {
      "id": 42,
      "race_number": 7,
      "name": "Auckland Cup",
      "meeting": {
        "id": 12,
        "track_name": "Ellerslie",
        "meeting_date": "2024-03-09",
        "surface": "turf",
        "jurisdiction": "NZ"
      },
      "distance_m": 3200,
      "race_class_code": "G1",
      "race_class_group": "group",
      "scheduled_start_time": "2024-03-09T03:30:00Z",
      "actual_start_time": "2024-03-09T03:32:00Z",
      "status": "finished",
      "prize_money": 400000
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `GET /races/{id}`

Get full race detail including entries.

**Response `200`:**
```json
{
  "id": 42,
  "race_number": 7,
  "name": "Auckland Cup",
  "meeting": { "..." },
  "distance_m": 3200,
  "race_class_code": "G1",
  "race_class_group": "group",
  "race_class_rank": 1,
  "scheduled_start_time": "2024-03-09T03:30:00Z",
  "actual_start_time": "2024-03-09T03:32:00Z",
  "status": "finished",
  "prize_money": 400000,
  "entries": [
    {
      "id": 201,
      "saddle_cloth": "5",
      "barrier_number": 5,
      "runner": {
        "id": 99,
        "name": "Rocket Man",
        "type": "thoroughbred",
        "country_of_origin": "NZ"
      },
      "jockey_or_driver": "J. McDonald",
      "trainer": "M. Baker",
      "weight_kg": 57.0,
      "scratched": false,
      "final_position": 1
    }
  ]
}
```

### `GET /races/{id}/timeline`

Canonical timeline events for a race, ordered by time.

**Response `200`:**
```json
{
  "race_id": 42,
  "actual_start_time": "2024-03-09T03:32:00Z",
  "events": [
    {
      "event_type": "barriers_loading",
      "event_time": "2024-03-09T03:31:30Z",
      "offset_ms": -30000,
      "source_type": "audio",
      "confidence": 0.91,
      "thumbnail_url": "https://media.betman.io/frames/feed_1/2024-03-09/frame_0120.jpg"
    },
    {
      "event_type": "actual_start",
      "event_time": "2024-03-09T03:32:00Z",
      "offset_ms": 0,
      "source_type": "ocr",
      "confidence": 0.98,
      "thumbnail_url": "https://media.betman.io/frames/feed_1/2024-03-09/frame_0135.jpg"
    },
    {
      "event_type": "finish",
      "event_time": "2024-03-09T03:35:18Z",
      "offset_ms": 198000,
      "source_type": "audio",
      "confidence": 0.97,
      "thumbnail_url": "https://media.betman.io/frames/feed_1/2024-03-09/frame_0388.jpg"
    }
  ]
}
```

### `GET /races/{id}/signals`

All raw signal observations for a race (OCR + audio events + scene classifications).

**Query parameters:** `type` (`ocr`, `audio`, `scene`) — filter by signal type.

### `GET /races/{id}/odds`

Odds snapshots for all entries in a race, suitable for rendering an odds table or drift chart.

**Response `200`:**
```json
{
  "race_id": 42,
  "actual_start_time": "2024-03-09T03:32:00Z",
  "entries": [
    {
      "race_entry_id": 201,
      "saddle_cloth": "5",
      "runner_name": "Rocket Man",
      "snapshots": [
        {"captured_at": "2024-03-09T03:00:00Z", "offset_ms": -7200000, "win_price": 4.20, "place_price": 1.80, "source": "api_feed"},
        {"captured_at": "2024-03-09T03:25:00Z", "offset_ms": -420000, "win_price": 3.40, "place_price": 1.55, "source": "api_feed"},
        {"captured_at": "2024-03-09T03:31:55Z", "offset_ms": -5000,   "win_price": 2.80, "place_price": 1.40, "source": "ocr_tote"}
      ]
    }
  ]
}
```

### `GET /races/{id}/odds-drift`

Chart-ready time-series odds data for a single runner or all runners.

**Query parameters:** `entry_id` — filter to one entry.

**Response `200`:**
```json
{
  "race_id": 42,
  "series": [
    {
      "label": "Rocket Man (#5)",
      "color": "#e63329",
      "data": [
        {"t": -7200000, "win": 4.20},
        {"t": -420000,  "win": 3.40},
        {"t": -5000,    "win": 2.80}
      ]
    }
  ]
}
```

### `GET /meetings?date=YYYY-MM-DD`

Returns meetings grouped by track with race counts and embedded races for the
requested date.

### `GET /races/{id}/odds-analysis`

Returns pre-computed odds analytics plus the most significant movement per
runner from `odds_analytics` and `odds_movements`.

### `GET /races/{id}/excitement`

Excitement score time-series for the race window — visualise as a waveform or gradient bar behind the replay timeline.

**Response `200`:**
```json
{
  "race_id": 42,
  "actual_start_time": "2024-03-09T03:32:00Z",
  "samples": [
    {"offset_ms": -180000, "score": 0.15, "scene": "parade_ring"},
    {"offset_ms": -30000,  "score": 0.62, "scene": "barriers"},
    {"offset_ms": 0,       "score": 0.88, "scene": "live_race"},
    {"offset_ms": 90000,   "score": 0.74, "scene": "live_race"},
    {"offset_ms": 195000,  "score": 0.98, "scene": "finish", "peak": true},
    {"offset_ms": 210000,  "score": 0.45, "scene": "replay"}
  ]
}
```

### `GET /races/{id}/scene-timeline`

Scene classification breakdown with keyframe thumbnails — the visual storyboard of a race.

**Response `200`:**
```json
{
  "race_id": 42,
  "scenes": [
    {"scene_type": "parade_ring",  "started_at_offset_ms": -360000, "ended_at_offset_ms": -120000, "thumbnail_url": "https://media.betman.io/frames/..."},
    {"scene_type": "barriers",     "started_at_offset_ms": -120000, "ended_at_offset_ms": -2000,   "thumbnail_url": "https://media.betman.io/frames/..."},
    {"scene_type": "live_race",    "started_at_offset_ms": 0,       "ended_at_offset_ms": 198000,  "thumbnail_url": "https://media.betman.io/frames/..."},
    {"scene_type": "finish",       "started_at_offset_ms": 195000,  "ended_at_offset_ms": 205000,  "thumbnail_url": "https://media.betman.io/frames/..."},
    {"scene_type": "replay",       "started_at_offset_ms": 205000,  "ended_at_offset_ms": 270000,  "thumbnail_url": "https://media.betman.io/frames/..."}
  ]
}
```

### `GET /races/{id}/replay` ⭐

**The centrepiece endpoint.** Returns a unified, time-ordered stream of commentary, race events, position calls, and odds updates — everything needed to replay a race from its audio narrative alone.

A front-end can step through `replay_frames` sequentially to reconstruct the full race experience as text + data, with no video required.

**Query parameters:**

| Param | Type | Description |
|---|---|---|
| `from_ms` | `integer` | Start offset in ms (default: first available, typically pre-race) |
| `to_ms` | `integer` | End offset in ms |
| `include` | `string` | Comma-separated: `commentary,events,odds,excitement` (default: all) |

**Response `200`:**
```json
{
  "race_id": 42,
  "race_name": "Auckland Cup",
  "meeting": "Ellerslie",
  "race_class": "G1",
  "distance_m": 3200,
  "actual_start_time": "2024-03-09T03:32:00Z",
  "duration_ms": 198000,
  "replay_frames": [
    {
      "offset_ms": -360000,
      "type": "commentary",
      "scene": "parade_ring",
      "text": "Good afternoon from Ellerslie. The horses for race seven, the Auckland Cup, are parading in the mounting yard...",
      "excitement_score": 0.12,
      "thumbnail_url": "https://media.betman.io/frames/feed_1/2024-03-09/frame_0001.jpg"
    },
    {
      "offset_ms": -120000,
      "type": "event",
      "event_type": "barriers_loading",
      "text": "Horses are making their way to the barriers",
      "excitement_score": 0.58,
      "thumbnail_url": "https://media.betman.io/frames/feed_1/2024-03-09/frame_0080.jpg"
    },
    {
      "offset_ms": -5000,
      "type": "odds_update",
      "runner_name": "Rocket Man",
      "saddle_cloth": "5",
      "win_price": 2.80,
      "place_price": 1.40,
      "market_status": "suspended"
    },
    {
      "offset_ms": 0,
      "type": "event",
      "event_type": "jump",
      "text": "And they're racing in the Auckland Cup!",
      "excitement_score": 0.88,
      "thumbnail_url": "https://media.betman.io/frames/feed_1/2024-03-09/frame_0135.jpg"
    },
    {
      "offset_ms": 45000,
      "type": "commentary",
      "scene": "live_race",
      "text": "At the 2400 metres, Rocket Man is striding clear on the outside, Thunder Ridge giving chase...",
      "excitement_score": 0.71,
      "thumbnail_url": "https://media.betman.io/frames/feed_1/2024-03-09/frame_0228.jpg",
      "positions": [
        {"position": 1, "runner_name": "Rocket Man",    "saddle_cloth": "5"},
        {"position": 2, "runner_name": "Thunder Ridge", "saddle_cloth": "2"}
      ]
    },
    {
      "offset_ms": 195000,
      "type": "commentary",
      "scene": "finish",
      "text": "It's Rocket Man! Rocket Man wins the Auckland Cup in a driving finish from Thunder Ridge!",
      "excitement_score": 0.98,
      "thumbnail_url": "https://media.betman.io/frames/feed_1/2024-03-09/frame_0388.jpg",
      "positions": [
        {"position": 1, "runner_name": "Rocket Man",    "saddle_cloth": "5"},
        {"position": 2, "runner_name": "Thunder Ridge", "saddle_cloth": "2"}
      ]
    },
    {
      "offset_ms": 210000,
      "type": "event",
      "event_type": "result_announced",
      "text": "Official result: 1st Rocket Man, 2nd Thunder Ridge",
      "excitement_score": 0.55
    }
  ]
}
```

### `GET /races/{id}/story`

AI-generated prose narrative of the race, produced from transcripts + timeline events after the race completes.

**Response `200`:**
```json
{
  "race_id": 42,
  "race_name": "Auckland Cup",
  "generated_at": "2024-03-09T04:10:00Z",
  "summary": "In a dramatic running of the 2024 Auckland Cup at Ellerslie, Rocket Man (barrier 5, ridden by J. McDonald) surged from midfield at the 600 metre mark to overhaul the brave leader Thunder Ridge in the final strides. The crowd's excitement peaked as the two leaders drew clear of the field inside the home straight. Rocket Man's winning margin was a head in a race run in 3:18.2, delivering trainer M. Baker a first Group 1 success at the meeting.",
  "key_moments": [
    {"offset_ms": 0,      "text": "Clean jump, Rocket Man settles midfield"},
    {"offset_ms": 90000,  "text": "Thunder Ridge makes a bold move to the lead"},
    {"offset_ms": 150000, "text": "Rocket Man launches from the outside"},
    {"offset_ms": 195000, "text": "Rocket Man wins — head margin at the line"}
  ],
  "winner_name": "Rocket Man",
  "margin_description": "a head",
  "model_version": "gpt-4o-2024-05-13"
}
```

### `GET /races/{id}/highlights`

Curated clip sequence for a race — the key moments as short video references.

**Response `200`:**
```json
{
  "race_id": 42,
  "clips": [
    {
      "clip_type": "pre_start",
      "label": "Parade Ring",
      "offset_ms": -360000,
      "duration_ms": 60000,
      "storage_uri": "clips/race_42/pre_start.mp4",
      "thumbnail_url": "https://media.betman.io/frames/..."
    },
    {
      "clip_type": "race_live",
      "label": "Full Race",
      "offset_ms": 0,
      "duration_ms": 198000,
      "storage_uri": "clips/race_42/live.mp4",
      "thumbnail_url": "https://media.betman.io/frames/..."
    },
    {
      "clip_type": "finish",
      "label": "Winning Moment",
      "offset_ms": 183000,
      "duration_ms": 20000,
      "storage_uri": "clips/race_42/finish.mp4",
      "thumbnail_url": "https://media.betman.io/frames/..."
    }
  ]
}
```

---

## Analytics

### `GET /analytics/trainer-win-rates`
### `GET /analytics/jockey-win-rates`

On-demand performance calculations from `race_entries`, `races`, and
`meetings`.

Supported filters:

- `track`
- `surface`
- `condition_category`
- `distance_min` / `distance_max`
- `race_class_group`
- `date_from` / `date_to`
- `min_runners`
- `order_by` (`win_rate`, `place_rate`, `roi`, `runners`)
- `group_by` (`track`, `barrier`)

Each row includes:

- runners
- wins
- places
- win rate
- place rate
- ROI where SP / closing price data is available

---

## Assistant

### `POST /assistant/query`

Natural-language exact search endpoint for the Data Viewer.

Request:

```json
{
  "question": "best jockeys at Flemington on soft tracks in the last 180 days"
}
```

Response includes:

- generated SQL
- bound parameters
- result rows
- natural-language summary
- confidence
- suggested chart spec

The query layer is guarded:

- read-only execution
- statement timeout
- single-`SELECT` enforcement
- allow-listed tables only
- required `LIMIT`

When no LLM key is configured, the endpoint falls back to deterministic
rule-based parsing for common BETMAN warehouse queries.

## 4. Runners

### `GET /runners/{id}`

Get runner detail.

### `GET /runners/{id}/form`

Historical race entries for a runner with results, race class, and media references.

**Response `200`:**
```json
{
  "runner_id": 99,
  "runner_name": "Rocket Man",
  "form": [
    {
      "race_id": 42,
      "race_name": "Auckland Cup",
      "race_class": "G1",
      "meeting_date": "2024-03-09",
      "track_name": "Ellerslie",
      "final_position": 1,
      "distance_m": 3200,
      "has_story": true,
      "has_replay": true,
      "highlight_clip_url": "clips/race_42/finish.mp4",
      "thumbnail_url": "https://media.betman.io/frames/..."
    }
  ]
}
```

---

## 5. Search

### `GET /search/ocr`

Full-text search over OCR-extracted text.

**Query parameters:** `q` (required), `race_class`, `date`, `limit`.

**Response `200`:**
```json
{
  "query": "Rocket Man",
  "results": [
    {
      "observation_id": 5541,
      "detected_text": "ROCKET MAN",
      "normalized_text": "Rocket Man",
      "observation_type": "runner_name",
      "frame_timestamp": "2024-03-09T03:32:05Z",
      "race_id": 42,
      "race_name": "Auckland Cup",
      "confidence": 0.96,
      "thumbnail_url": "https://media.betman.io/frames/..."
    }
  ]
}
```

### `GET /search/transcripts`

Full-text search over ASR transcript segments.

**Query parameters:** `q` (required), `race_class`, `date`, `scene`, `limit`.

**Response `200`:**
```json
{
  "query": "wins the Auckland Cup",
  "results": [
    {
      "transcript_id": 8812,
      "text": "It's Rocket Man! Rocket Man wins the Auckland Cup in a driving finish from Thunder Ridge!",
      "started_at": "2024-03-09T03:35:15Z",
      "race_offset_ms": 195000,
      "race_id": 42,
      "race_name": "Auckland Cup",
      "race_class": "G1",
      "excitement_score": 0.98,
      "thumbnail_url": "https://media.betman.io/frames/..."
    }
  ]
}
```

### `GET /search/similar`

Find races similar to a given race using vector embedding similarity.

**Query parameters:** `race_id` (required), `limit` (default 10), `embedding_type` (`commentary`, `audio`, `combined`).

**Response `200`:**
```json
{
  "race_id": 42,
  "similar_races": [
    {
      "race_id": 17,
      "race_name": "Waikato Draught Spring Classic",
      "race_class": "G1",
      "meeting_date": "2023-10-14",
      "track_name": "Te Rapa",
      "similarity_score": 0.91,
      "similarity_reason": "Similar commentary arc — prominent late challenge, close finish",
      "thumbnail_url": "https://media.betman.io/frames/..."
    }
  ]
}
```

---

## 6. Events

### `GET /events`

Query derived race events across all races.

**Query parameters:**

| Param | Type | Description |
|---|---|---|
| `type` | `string` | e.g. `race_call`, `jump_imminent`, `protest`, `result_announced` |
| `feed_id` | `integer` | Filter by feed |
| `race_class` | `string` | Filter by race class |
| `since` | `ISO 8601` | Events after this time |
| `limit` | `integer` | Max results |

**Response `200`:**
```json
{
  "events": [
    {
      "id": 3301,
      "event_type": "jump_imminent",
      "predicted_at": "2024-03-09T03:31:55Z",
      "race_id": 42,
      "race_name": "Auckland Cup",
      "confidence": 0.93,
      "source_type": "audio"
    }
  ]
}
```

---

## 7. Skin Engine (Public)

Used by tenant front-ends to resolve their active branding configuration.

### `GET /skins/{tenant_slug}`

Resolve the active skin for a tenant, optionally scoped to a context.

**Query parameters:**

| Param | Type | Description |
|---|---|---|
| `race_class` | `string` | e.g. `G1` — activate a class-specific skin |
| `meeting_id` | `integer` | Activate a meeting-specific skin |
| `race_id` | `integer` | Activate a race-specific skin |

**Response `200`:**
```json
{
  "tenant": "ladbrokes",
  "skin_id": 3,
  "skin_name": "Ladbrokes Dark",
  "context_type": "race_class",
  "context_ref": "G1",
  "config": {
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
  },
  "assets": {
    "logo": "https://cdn.betman.io/tenants/ladbrokes/logo.svg",
    "logo_dark": "https://cdn.betman.io/tenants/ladbrokes/logo-dark.svg",
    "favicon": "https://cdn.betman.io/tenants/ladbrokes/favicon.png",
    "sponsor_logo": "https://cdn.betman.io/tenants/ladbrokes/sponsor.png"
  },
  "active_ads": [
    {
      "slot": "pre_race_banner",
      "creative_url": "https://cdn.betman.io/ads/ladbrokes/g1-banner-728x90.jpg",
      "click_url": "https://www.ladbrokes.com.au/racing/auckland-cup",
      "dimensions": "728x90"
    },
    {
      "slot": "replay_overlay_top",
      "creative_url": "https://cdn.betman.io/ads/ladbrokes/g1-replay-overlay.png",
      "click_url": "https://www.ladbrokes.com.au/racing",
      "dimensions": "970x60"
    }
  ]
}
```

### `GET /skins/{tenant_slug}/ads`

Get active ad placements for a skin and slot.

**Query parameters:** `slot` (required) — slot code e.g. `pre_race_banner`.

---

## 8. Admin API

> Admin endpoints require elevated privileges (`Authorization: ******  
> All admin routes are prefixed `/admin/`.

### Tenants

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/tenants` | List all tenants |
| `POST` | `/admin/tenants` | Create a tenant |
| `GET` | `/admin/tenants/{id}` | Get tenant detail |
| `PATCH` | `/admin/tenants/{id}` | Update tenant |
| `DELETE` | `/admin/tenants/{id}` | Deactivate tenant |

**`POST /admin/tenants` body:**
```json
{
  "name": "Ladbrokes",
  "slug": "ladbrokes",
  "contact_email": "tech@ladbrokes.com.au",
  "license_type": "full",
  "license_expires_at": "2026-12-31T00:00:00Z"
}
```

### Skins

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/tenants/{id}/skins` | List skins for a tenant |
| `POST` | `/admin/tenants/{id}/skins` | Create a skin |
| `GET` | `/admin/skins/{id}` | Get skin detail |
| `PATCH` | `/admin/skins/{id}` | Update skin config |
| `DELETE` | `/admin/skins/{id}` | Deactivate skin |
| `POST` | `/admin/skins/{id}/set-default` | Set as tenant default |

**`POST /admin/tenants/{id}/skins` body:**
```json
{
  "name": "Ladbrokes Dark",
  "slug": "ladbrokes-dark",
  "is_default": true,
  "config_json": {
    "colors": {"primary": "#e63329", "background": "#0d0d0d"},
    "features": {"commentary_replay": true, "race_story": true}
  }
}
```

### Skin Assets

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/skins/{id}/assets` | List assets for a skin |
| `POST` | `/admin/skins/{id}/assets` | Upload an asset (`multipart/form-data`) |
| `DELETE` | `/admin/skins/{id}/assets/{asset_id}` | Delete an asset |

**`POST /admin/skins/{id}/assets` fields:** `asset_type`, `label`, `file` (binary upload).

### Skin Contexts

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/skins/{id}/contexts` | List contexts for a skin |
| `POST` | `/admin/skins/{id}/contexts` | Add a context |
| `DELETE` | `/admin/skins/{id}/contexts/{ctx_id}` | Remove a context |

**`POST /admin/skins/{id}/contexts` body:**
```json
{
  "context_type": "race_class",
  "context_ref": "G1",
  "priority": 10
}
```

### Ad Slots & Placements

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/ad-slots` | List available ad slot types |
| `GET` | `/admin/skins/{id}/ads` | List ad placements for a skin |
| `POST` | `/admin/skins/{id}/ads` | Create an ad placement |
| `PATCH` | `/admin/skins/{id}/ads/{placement_id}` | Update a placement |
| `DELETE` | `/admin/skins/{id}/ads/{placement_id}` | Remove a placement |

**`POST /admin/skins/{id}/ads` body:**
```json
{
  "slot_type_id": 2,
  "asset_id": 15,
  "label": "G1 Pre-Race Banner",
  "click_url": "https://www.ladbrokes.com.au/racing/auckland-cup",
  "active_from": "2024-03-01T00:00:00Z",
  "active_until": "2024-03-31T23:59:59Z",
  "priority": 5
}
```

---

## 9. Real-Time WebSocket

### `WS /live/{feed_id}`

Subscribe to a real-time stream of race events as they are detected from the live feed.

**Connection:** `wss://data-api.betman.internal/v1/live/1`

Clients receive JSON messages as events are detected:

```json
{"type": "commentary", "offset_ms": 45000, "race_id": 42, "text": "Rocket Man leads at the 800...", "excitement_score": 0.71}
{"type": "event",      "offset_ms": 195000, "race_id": 42, "event_type": "finish", "excitement_score": 0.98}
{"type": "odds_update","race_id": 42, "runner_name": "Rocket Man", "win_price": 2.80, "market_status": "suspended"}
{"type": "scene_change","feed_id": 1, "scene_type": "live_race", "thumbnail_url": "https://..."}
{"type": "heartbeat",  "timestamp": "2024-03-09T03:32:05Z"}
```

**Tenant-scoped:** Authenticate with a tenant API key to receive only events relevant to your licensed content scope.

---

## 10. Tracks — Barrier Analysis, Weather & Conditions

### `GET /tracks/{track_name}/barriers`

Barrier win/place statistics for a track, filterable by condition, surface, distance, and race class.

**Query parameters:**

| Param | Type | Description |
|---|---|---|
| `condition` | `string` | Exact code: `H10`, `S6`, `G4`, etc. |
| `condition_category` | `string` | `heavy`, `soft`, `good`, `firm` |
| `surface` | `string` | `turf`, `synthetic` |
| `distance_min` | `integer` | Min distance metres |
| `distance_max` | `integer` | Max distance metres |
| `race_class_group` | `string` | `group`, `handicap`, `maiden`, etc. |
| `field_size_min` | `integer` | Min field size |
| `since` | `date` | Only include races from this date |

**Response `200`:**
```json
{
  "track_name": "Ellerslie",
  "surface": "turf",
  "filters": {
    "condition_code": "H10",
    "distance_band": "1400-1600",
    "since": "2021-01-01"
  },
  "sample_size": 847,
  "barriers": [
    {
      "barrier_number": 1,
      "relative_barrier": "inside_third",
      "total_runners": 71,
      "wins": 14,
      "places": 29,
      "win_rate": 0.197,
      "place_rate": 0.408,
      "avg_win_price": 4.20,
      "rank_by_win_rate": 1
    },
    {
      "barrier_number": 2,
      "relative_barrier": "inside_third",
      "total_runners": 68,
      "wins": 11,
      "places": 24,
      "win_rate": 0.162,
      "place_rate": 0.353,
      "avg_win_price": 5.10,
      "rank_by_win_rate": 2
    }
  ]
}
```

### `GET /tracks/{track_name}/heatmap`

Spatial heat map data — intensity values per track zone and condition, ready to render over a track diagram.

**Query parameters:** `condition_category`, `surface`, `distance_band`.

**Response `200`:**
```json
{
  "track_name": "Ellerslie",
  "condition_category": "heavy",
  "cells": [
    {"zone": "rail",    "distance_from_finish_band": "0-200",   "win_rate": 0.24, "intensity": 1.0},
    {"zone": "inside",  "distance_from_finish_band": "0-200",   "win_rate": 0.19, "intensity": 0.79},
    {"zone": "middle",  "distance_from_finish_band": "0-200",   "win_rate": 0.14, "intensity": 0.58},
    {"zone": "outside", "distance_from_finish_band": "0-200",   "win_rate": 0.08, "intensity": 0.33}
  ]
}
```

### `GET /tracks/{track_name}/conditions`

Current and recent track condition readings.

**Response `200`:**
```json
{
  "track_name": "Ellerslie",
  "current_condition": {
    "condition_code": "H10",
    "condition_category": "heavy",
    "penetrometer_value": 3.8,
    "recorded_at": "2024-03-09T07:00:00Z",
    "source": "official"
  },
  "recent_readings": [
    {"recorded_at": "2024-03-09T07:00:00Z", "condition_code": "H10", "penetrometer_value": 3.8},
    {"recorded_at": "2024-03-08T18:00:00Z", "condition_code": "H9",  "penetrometer_value": 4.1}
  ]
}
```

### `GET /tracks/{track_name}/weather`

Live and historical weather data for a track's WeatherLink station.

**Query parameters:** `since` (ISO 8601), `resolution` (`raw`, `hourly`, `daily`).

**Response `200`:**
```json
{
  "track_name": "Ellerslie",
  "station_label": "Ellerslie Main Station",
  "current": {
    "recorded_at": "2024-03-09T08:45:00Z",
    "temperature_c": 14.2,
    "humidity_pct": 91.0,
    "wind_speed_kmh": 18.0,
    "wind_direction_deg": 225,
    "rainfall_1h_mm": 4.2,
    "rainfall_24h_mm": 38.6,
    "barometric_pressure_hpa": 1008.2
  },
  "soil_moisture": [
    {"probe_label": "rail_100m",    "zone": "rail",    "moisture_pct": 52.3},
    {"probe_label": "centre_400m",  "zone": "centre",  "moisture_pct": 47.1},
    {"probe_label": "outside_800m", "zone": "outside", "moisture_pct": 44.8}
  ],
  "history": []
}
```

### `GET /races/{id}/barrier-context`

For a specific race: show each entry's barrier alongside current barrier statistics for this track/condition. Useful for pre-race analysis UI.

**Response `200`:**
```json
{
  "race_id": 42,
  "track_name": "Ellerslie",
  "condition_code": "H10",
  "entries": [
    {
      "saddle_cloth": "5",
      "runner_name": "Rocket Man",
      "barrier_number": 5,
      "field_size": 14,
      "relative_barrier": "middle_third",
      "barrier_stats": {
        "win_rate": 0.14,
        "place_rate": 0.32,
        "sample_size": 68,
        "rank_by_win_rate": 6
      }
    }
  ]
}
```

---

## 11. Odds Intelligence

### `GET /races/{id}/odds-analysis`

Full odds movement analysis for a race — the complete picture of market behaviour from open to suspension.

**Response `200`:**
```json
{
  "race_id": 42,
  "race_name": "Auckland Cup",
  "scheduled_start_time": "2024-03-09T03:30:00Z",
  "entries": [
    {
      "race_entry_id": 201,
      "runner_name": "Rocket Man",
      "saddle_cloth": "5",
      "opening_price": 4.20,
      "closing_price": 2.80,
      "min_price": 2.80,
      "max_price": 4.20,
      "total_movement_pct": -33.3,
      "steam_detected": true,
      "blowout_detected": false,
      "firmings_count": 8,
      "driftings_count": 1,
      "biggest_move": {"type": "steam", "pct": -18.5, "detected_at": "2024-03-09T03:20:00Z", "time_to_jump_s": 600}
    }
  ],
  "notable_movements": [
    {
      "runner_name": "Rocket Man",
      "saddle_cloth": "5",
      "type": "steam",
      "from_price": 3.80,
      "to_price": 2.80,
      "movement_pct": -26.3,
      "detected_at": "2024-03-09T03:20:00Z",
      "time_to_jump_s": 600
    }
  ]
}
```

### `GET /races/{id}/odds-timeline`

Chart-ready time series of all odds snapshots for all entries from market open to suspension. Ideal for rendering an animated odds drift visualisation.

---

## 12. Admin — WeatherLink & API Keys

> Admin routes prefixed `/admin/`, require elevated API key.

### Weather Stations

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/weather-stations` | List all weather stations |
| `POST` | `/admin/weather-stations` | Add a weather station |
| `GET` | `/admin/weather-stations/{id}` | Get station detail + probe list |
| `PATCH` | `/admin/weather-stations/{id}` | Update station config |
| `DELETE` | `/admin/weather-stations/{id}` | Deactivate station |
| `GET` | `/admin/weather-stations/{id}/probes` | List soil moisture probes |
| `POST` | `/admin/weather-stations/{id}/probes` | Add a probe |
| `PATCH` | `/admin/weather-stations/{id}/probes/{probe_id}` | Update probe metadata |

**`POST /admin/weather-stations` body:**
```json
{
  "track_name": "Ellerslie",
  "station_id": "119061",
  "api_key_config_id": 3,
  "label": "Ellerslie Main Station",
  "latitude": -36.8729,
  "longitude": 174.8156,
  "elevation_m": 14
}
```

### External API Keys

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/api-keys` | List configured integrations (keys redacted) |
| `POST` | `/admin/api-keys` | Add an API key config |
| `PATCH` | `/admin/api-keys/{id}` | Update key or endpoint |
| `DELETE` | `/admin/api-keys/{id}` | Deactivate key |
| `POST` | `/admin/api-keys/{id}/test` | Test connectivity to the external service |

**`POST /admin/api-keys` body:**
```json
{
  "service_name": "weatherlink",
  "key_name": "WeatherLink Ellerslie",
  "api_key": "wl_live_XXXX",
  "endpoint_url": "https://api.weatherlink.com/v2",
  "extra_config_json": {"station_id": "119061"}
}
```

### Tenant Feed Assignment

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/tenants/{id}/feeds` | List feeds assigned to a tenant |
| `POST` | `/admin/tenants/{id}/feeds` | Assign a feed to a tenant |
| `PATCH` | `/admin/tenants/{id}/feeds/{feed_id}` | Update feed config (override URL, quality) |
| `DELETE` | `/admin/tenants/{id}/feeds/{feed_id}` | Remove feed from tenant |

**`POST /admin/tenants/{id}/feeds` body:**
```json
{
  "feed_id": 1,
  "override_url": "https://private-stream.racingcom.co.nz/trackside1/master.m3u8",
  "quality_preference": "high"
}
```


```json
{
  "error": "not_found",
  "message": "Race 9999 not found",
  "detail": {"race_id": 9999}
}
```

| Code | Error | Description |
|---|---|---|
| `400` | `bad_request` | Invalid query parameters |
| `401` | `unauthorized` | Missing or invalid API key |
| `403` | `forbidden` | Feature not available on tenant license |
| `404` | `not_found` | Resource not found |
| `429` | `rate_limited` | Too many requests |
| `500` | `internal_error` | Unexpected server error |
