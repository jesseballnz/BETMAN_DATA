# BETMAN_DATA — Launch Readiness

**Date:** 2026-06-25  
**Status:** ⚠️ Conditional — blockers identified, go/no-go below

---

## Go / No-Go Checklist

### ✅ Green — Ready

| Item | Evidence |
|------|----------|
| Core racing data endpoints wired | `meetings`, `races`, `tracks`, `race_entries` all execute real SQL |
| Market intelligence wired | `market` router (signals, steamers, drifters, smart money, odds ticks) |
| Discovery patterns wired | `discovery` router (patterns, signals, runs) |
| Analytics wired | `analytics` router (trainer/jockey win rates via SQL) |
| Intelligence scores wired | `intelligence` router (race scores, pre-race intel, leaderboard) |
| Pedigree canonicalized | `pedigree` router fully wired; `horse_uuid` canonical identity added to runners + pedigrees via migration 005 |
| No fabricated data | No synthetic "Unknown" or hardcoded row stubs remain in wired endpoints |
| Auth + rate limiting | TenantMiddleware, API key auth, Redis rate limiting, daily quota all in place |
| Security headers | `SecurityHeadersMiddleware` adds CSP, HSTS, X-Frame-Options, etc. |
| Migrations idempotent | All 5 migrations use `IF NOT EXISTS` / `ON CONFLICT DO NOTHING` |
| Migration tracking | All migrations self-register in `schema_migrations` |
| CI lint/test passing | `ruff check` and `pytest` pass on every PR |
| WebSocket live feed | `/v1/live/{feed_id}` with Redis pub/sub and heartbeat |
| Feeds wired | `feeds` router now queries `feeds` + `stream_sessions` tables |
| Runners detail wired | `GET /runners/{runner_id}` queries `runners` table; 404 on miss |
| Admin CRUD wired | Tenant/key/skin CRUD in `admin` router is DB-backed |

### ⚠️ Amber — Known Gaps (not blockers)

| Item | Current state | Risk |
|------|--------------|------|
| Pedigree data population | Tables exist and are wired; real horse pedigree data must be ingested via provider pipeline | Medium — empty responses until data is loaded |
| `horse_uuid` backfill | `runners.horse_uuid` column added by migration 005; values must be populated by ingestion | Medium — pedigree by-UUID lookup returns 404 until ingested |
| Skin resolution | `GET /skins/{tenant_slug}` returns 501; tenants/skins tables exist but resolver not implemented | Medium — OEM skin feature not usable |
| Runner form history | `GET /runners/{runner_id}/form` returns 501; media/story pipeline not linked | Low — race results available via `/races/{id}` |
| Admin asset upload | File upload to object storage not implemented | Low — manual asset injection required |

### 🔴 Red — Blockers

| Item | Current state | Action required |
|------|--------------|----------------|
| Search endpoints | OCR, transcript, similarity search all return 501 | Implement full-text search or leave as intentional 501 until pipeline is ready |
| Event streaming | `GET /v1/events` returns 501 | Wire to `race_timeline_events` or accept 501 until event pipeline complete |
| `provider_entity_mappings` population | Table exists; no ingestion code verified to populate it | Verify ingest pipeline populates `entity_type = 'runner'` rows before pedigree lookups will resolve |

---

## Quality Gates

| Gate | Status | Command |
|------|--------|---------|
| Python lint (ruff) | ✅ Passing | `python -m ruff check services/ libs/` |
| Unit/contract tests (pytest) | ✅ Passing | `python -m pytest tests -q` |
| Webapp lint/build | Not touched (no webapp changes in Pass 3) | `cd services/webapp && npm run lint && npm run build` |
| Migration idempotency | ✅ All 5 migrations safe to re-run | `make migrate` |

---

## Migration State

| File | Status |
|------|--------|
| `001_initial_schema.sql` | ✅ Applied |
| `002_intelligence_layers.sql` | ✅ Applied |
| `003_pedigree_and_providers.sql` | ✅ Applied (partial — `pedigrees` CREATE silently skipped; provider_entity_mappings created) |
| `004_api_keys_and_security.sql` | ✅ Applied |
| `005_pedigree_reconciliation.sql` | ✅ New — adds `horse_uuid` to runners + pedigrees; must be applied before deploying Pass 3 API |

---

## Pass 4 Backlog

Items seeded from the API/schema drift audit:

1. **Skin resolution** — Wire `GET /skins/{tenant_slug}` to `tenants` + `skins` + `skin_contexts` tables with context priority hierarchy.
2. **Runner form history** — Wire `GET /runners/{runner_id}/form` with race results, media links (`clips`, `race_summaries`).
3. **Event querying** — Wire `GET /events` to `race_timeline_events` with filters.
4. **OCR search** — Add `tsvector` index to `ocr_observations` and wire `/search/ocr`.
5. **Transcript search** — Add `tsvector` index to `transcript_segments` and wire `/search/transcripts`.
6. **Embedding similarity** — Wire `/search/similar` to pgvector cosine distance on `runner_embeddings`.
7. **Pedigree ingestion** — Verify and/or build the ingestion pipeline that populates `pedigrees.horse_uuid` and `runners.horse_uuid` from provider data.
8. **Admin asset upload** — Implement S3/object-storage upload in `admin.py`.
9. **Provider entity mapping audit** — Confirm ingestion populates `entity_type = 'runner'` rows in `provider_entity_mappings`.
10. **`provider_name` on pedigrees** — Ensure ingestion pipeline sets `pedigrees.provider_name` to source identifier (e.g., `loveracing`, `racing_australia`).

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Pedigree tables empty at launch | High | Low | Endpoints return honest 404/empty; no fabricated data |
| `horse_uuid` not backfilled before launch | High | Low | Pedigree by-UUID returns 404; runner_id lookup still works |
| Migration 003 silently no-op'd on new installs | Low | Medium | Migration 005 adds the missing columns; both 003+005 together are idempotent |
| Search/events 501 responses confuse consumers | Medium | Low | Document in OpenAPI descriptions; 501 is explicit and self-documenting |
| Skins 501 blocks OEM tenant onboarding | High | High | Implement skin resolution before OEM launch (Pass 4 priority 1) |
