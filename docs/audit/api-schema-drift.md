# API ↔ Schema Drift Audit — Pass 3

**Date:** 2026-06-25  
**Scope:** All `/v1` routers registered in `services/api/app/main.py`  
**Migrations audited:** 001 – 005

---

## Classification Legend

| Status | Meaning |
|--------|---------|
| **wired** | Endpoint executes real SQL against the DB; response model matches actual columns |
| **partial** | Some endpoints in the router are wired; others return 501 or empty without querying |
| **stub-or-empty-200** | Endpoint always returns a success response without any DB query — fabricated data or silent no-op |

---

## Router Classification Table

| Router prefix | File | Status | Notes |
|---------------|------|--------|-------|
| `/v1/health` | `health.py` | **wired** | Queries DB and Redis for liveness/readiness |
| `/v1/metrics` | `metrics.py` | **wired** | Serves Prometheus text from in-process middleware snapshot |
| `/v1/stats` | `stats.py` | **wired** | Queries pg_class, counts, freshness; fully DB-backed |
| `/v1/meetings` | `meetings.py` | **wired** | SELECT + GROUP BY with race counts |
| `/v1/races` | `races.py` | **wired** | Full race detail, entries, barrier context, odds analysis |
| `/v1/runners` | `runners.py` | **partial** | `GET /{runner_id}` wired (Pass 3); `GET /{runner_id}/form` → 501 |
| `/v1/tracks` | `tracks.py` | **wired** | Track list, barrier stats, heatmap — all DB-backed |
| `/v1/intelligence` | `intelligence.py` | **wired** | Race scores, pre-race intel, horse score history, leaderboard |
| `/v1/market` | `market.py` | **wired** | Signals, steamers, drifters, smart money, odds ticks, tote pools |
| `/v1/discovery` | `discovery.py` | **wired** | Patterns, signals, runs, gate-bias patterns — all DB-backed |
| `/v1/analytics` | `analytics.py` | **wired** | Trainer and jockey win rates via SQL aggregation |
| `/v1/assistant` | `assistant.py` | **wired** | NLP → SQL via `resolve_plan`; executes readonly query |
| `/v1/compliance` | `compliance.py` | **wired** | Static rules + jurisdiction lookup (no DB needed) |
| `/v1/admin` | `admin.py` | **partial** | CRUD for tenants/keys/skins wired; asset upload and encryption TODOs remain |
| `/v1/feeds` | `feeds.py` | **wired** | Pass 3: now queries `feeds` + `stream_sessions` tables |
| `/v1/live` | `live.py` | **wired** | WebSocket with Redis pub/sub; auth via `TenantMiddleware` |
| `/v1/pedigree` | `pedigree.py` | **wired** | Pass 3: all four endpoints now query `pedigrees`, `bloodline_performance`, `pedigree_affinities` |
| `/v1/skins` | `skins.py` | **partial** | `GET /{tenant_slug}` → 501; `GET /{tenant_slug}/ads` → honest null |
| `/v1/events` | `events.py` | **stub-or-empty-200** → **501** | Pass 3: converted to explicit 501 |
| `/v1/search` | `search.py` | **stub-or-empty-200** → **501** | Pass 3: all three endpoints converted to 501 |

---

## Detailed Endpoint Inventory

### `/v1/pedigree` — Pass 3 changes

| Method | Path | Before | After | DB table |
|--------|------|--------|-------|----------|
| GET | `/pedigree/horses/{runner_id}` | Returns fabricated `runner_name="Unknown"` | Real SELECT; 404 on miss | `pedigrees JOIN runners` |
| GET | `/pedigree/horses/by-uuid/{horse_uuid}` | _did not exist_ | New canonical endpoint; 404 on miss | `pedigrees JOIN runners` |
| GET | `/pedigree/sires/{sire_name}/performance` | Returns `[]` (TODO) | Real SELECT; `[]` = honest no data | `bloodline_performance` |
| GET | `/pedigree/sires/{sire_name}/affinities` | Returns `[]` (TODO) | Real SELECT; `[]` = honest no data | `pedigree_affinities` |
| GET | `/pedigree/sires/top-wet-track` | Returns `[]` (TODO) | Real SELECT; `[]` = honest no data | `bloodline_performance` |

### `/v1/pedigree` — Schema drift resolved by migration 005

| Issue | Migration 003 intent | Migration 002 reality | Resolution (005) |
|-------|---------------------|----------------------|-----------------|
| `pedigrees.horse_uuid` | Created as primary key column | Missing (002's `runner_id`-keyed table was not replaced) | `ALTER TABLE pedigrees ADD COLUMN IF NOT EXISTS horse_uuid UUID` |
| `pedigrees.provider_name` | Created in 003 | Missing | `ALTER TABLE pedigrees ADD COLUMN IF NOT EXISTS provider_name TEXT` |
| `pedigrees.updated_at` | Created in 003 | Missing | `ALTER TABLE pedigrees ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ` |
| `runners.horse_uuid` | Not addressed in 003 | Missing | `ALTER TABLE runners ADD COLUMN IF NOT EXISTS horse_uuid UUID` |
| `idx_pedigrees_horse_uuid` | Guarded by column existence check | Never created | Created unconditionally in 005 after column is added |

### `/v1/runners` — Pass 3 changes

| Method | Path | Before | After | DB table |
|--------|------|--------|-------|----------|
| GET | `/runners/{runner_id}` | Returns `{"runner_id": runner_id}` stub | Real SELECT; 404 on miss | `runners` |
| GET | `/runners/{runner_id}/form` | Returns empty `RunnerFormResponse` | 501 (pending media pipeline) | — |

### `/v1/feeds` — Pass 3 changes

| Method | Path | Before | After | DB table |
|--------|------|--------|-------|----------|
| GET | `/feeds` | Hardcoded list of 2 Trackside URLs | Real SELECT from `feeds` | `feeds + stream_sessions` |
| GET | `/feeds/{feed_id}` | Returns `{"feed_id": feed_id}` stub | Real SELECT; 404 on miss | `feeds + stream_sessions` |

### `/v1/events` — Pass 3 changes

| Method | Path | Before | After |
|--------|------|--------|-------|
| GET | `/events` | Returns `{"events": [], "limit": ...}` | 501 Not Implemented |

### `/v1/search` — Pass 3 changes

| Method | Path | Before | After |
|--------|------|--------|-------|
| GET | `/search/ocr` | Returns `{"results": []}` | 501 Not Implemented |
| GET | `/search/transcripts` | Returns `{"results": []}` | 501 Not Implemented |
| GET | `/search/similar` | Returns `{"similar_races": []}` | 501 Not Implemented |

### `/v1/skins` — Pass 3 changes

| Method | Path | Before | After |
|--------|------|--------|-------|
| GET | `/skins/{tenant_slug}` | Returns fabricated default skin config | 501 Not Implemented |
| GET | `/skins/{tenant_slug}/ads` | Returns `{"ad": None}` | Unchanged — honest null response |

---

## Response Model ↔ DB Column Cross-check

### `pedigrees` table (post migration 005)

| Column | API field | Match? |
|--------|-----------|--------|
| `id` | — (internal) | ✅ |
| `runner_id` | `PedigreeDetail.runner_id` | ✅ |
| `horse_uuid` | `PedigreeDetail.horse_uuid` | ✅ |
| `sire` | `PedigreeDetail.sire` | ✅ |
| `dam` | `PedigreeDetail.dam` | ✅ |
| `damsire` | `PedigreeDetail.damsire` | ✅ |
| `grandsire_pat` | `PedigreeDetail.grandsire_pat` | ✅ |
| `grandsire_mat` | `PedigreeDetail.grandsire_mat` | ✅ |
| `family_line` | `PedigreeDetail.family_line` | ✅ |
| `colour` | `PedigreeDetail.colour` | ✅ |
| `provider_name` | `PedigreeDetail.provider_name` | ✅ |
| `updated_at` | — (internal) | ✅ |

### `bloodline_performance` table

| Column | API field | Match? |
|--------|-----------|--------|
| `sire` | `SirePerformanceItem.sire` | ✅ |
| `track_name` | `SirePerformanceItem.track_name` | ✅ |
| `surface` | `SirePerformanceItem.surface` | ✅ |
| `condition_category` | `SirePerformanceItem.condition_category` | ✅ |
| `distance_band` | `SirePerformanceItem.distance_band` | ✅ |
| `runners` | `SirePerformanceItem.runners` | ✅ |
| `wins` | `SirePerformanceItem.wins` | ✅ |
| `win_rate` | `SirePerformanceItem.win_rate` | ✅ |
| `place_rate` | `SirePerformanceItem.place_rate` | ✅ |
| `avg_win_price` | `SirePerformanceItem.avg_win_price` | ✅ |
| `roi` | `SirePerformanceItem.roi` | ✅ |

### `pedigree_affinities` table

| Column | API field | Match? |
|--------|-----------|--------|
| `sire` | `SireAffinityItem.sire` | ✅ |
| `affinity_type` | `SireAffinityItem.affinity_type` | ✅ |
| `context_track` | `SireAffinityItem.context_track` | ✅ |
| `context_distance_band` | `SireAffinityItem.context_distance_band` | ✅ |
| `context_condition` | `SireAffinityItem.context_condition` | ✅ |
| `affinity_score` | `SireAffinityItem.affinity_score` | ✅ |
| `win_rate` | `SireAffinityItem.win_rate` | ✅ |
| `sample_size` | `SireAffinityItem.sample_size` | ✅ |

---

## Remaining Drift Items (Pass 4 backlog)

| Item | Router | Priority |
|------|--------|----------|
| Skin resolution from DB (`tenants`, `skins`, `skin_contexts` tables) | `skins.py` | High |
| Runner form history with media linkage | `runners.py` | Medium |
| Event querying from `race_timeline_events` | `events.py` | Medium |
| OCR full-text search (`ocr_observations` table with `pg_trgm`) | `search.py` | Medium |
| Transcript full-text search (`transcript_segments` table) | `search.py` | Medium |
| Embedding similarity search (pgvector on `runner_embeddings`) | `search.py` | Low |
| Admin: asset upload to object storage | `admin.py` | Medium |
| Admin: per-service connectivity test | `admin.py` | Low |
| Verify `provider_entity_mappings` is populated by ingestion | `pedigree.py` | High |
