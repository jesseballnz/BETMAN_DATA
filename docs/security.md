# BETMAN_DATA security deep dive

## Threat model

BETMAN_DATA is a multi-tenant licensing platform. The highest-risk areas are:

- cross-tenant data leakage
- admin key misuse
- browser-tier secret exposure
- unsafe assistant query execution
- incomplete observability around privileged actions

## Current controls

### Secrets and configuration

- compose secrets are sourced from the root `.env`
- `.env.example` documents every stack variable with safe placeholders
- the webapp proxy is intended to use a read-only tenant key, not the admin key

### Authentication and authorization

- API auth uses `Authorization: ******`
- tenant keys are stored as deterministic PBKDF2-HMAC hashes with a lookup prefix
- admin routes require admin-scoped keys
- inactive tenants, expired licenses, and expired keys are denied

### Transport and browser protections

- CORS is an explicit allow-list via `CORS_ORIGINS`
- security headers are set in FastAPI and mirrored in nginx:
  - `Content-Security-Policy`
  - `Referrer-Policy: no-referrer`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Strict-Transport-Security` outside development

### Abuse protection

- **Redis-backed per-tenant/path rate limiting** using an atomic Lua fixed-window
  counter (`INCR` + `EXPIRE`).  Each worker shares the same Redis state, so the
  limit is accurate even when the API runs with `--workers N`.
  `Retry-After` is derived from the Redis key TTL for accuracy.
- Optional daily quotas are also tracked in Redis (per-tenant day-bucket counter)
  and reconciled against `tenant_usage` for billing truth.  Both types of excess
  return `429` with a `Retry-After` header.
- **Graceful degradation:** if Redis is unavailable the rate limiter falls back
  to an in-process fixed-window dict and logs a single `rate_limit.redis_unavailable`
  WARNING per burst — no `500` responses, no stack-trace flood.

### Metrics endpoint (`/v1/metrics`)

Per-path request volume and latency telemetry is **not public by default**.

| Setting | Behaviour |
|---------|-----------|
| `METRICS_PUBLIC=false` (default) | `/v1/metrics` requires an admin-scoped API key |
| `METRICS_PUBLIC=true` | `/v1/metrics` is accessible without auth (suitable for an internal scrape proxy) |

`/v1/health` and `/v1/ready` remain public regardless of this setting.

### Compliance and auditability

- `/v1/compliance/rules` exposes jurisdiction metadata and responsible-gambling messaging
- admin key operations write `audit_log`
- assistant responses include a "data and insights, not betting advice" disclaimer

### Schema self-check at startup

On startup, the API queries `information_schema.columns` to verify that every
table/column the middleware and routers write to actually exists in the live
database.  If any object is missing a `schema.missing_object` WARNING is emitted
(non-fatal) so operators are alerted immediately rather than receiving per-request
exception spam.

## Operational guidance

- rotate admin and read-only proxy keys independently
- keep the proxy key scoped to `read`
- monitor `/v1/ready` and `/v1/metrics` (use an admin key for the metrics scrape)
- review `tenant_usage` and `audit_log` as part of billing and security operations
- run `make migrate` after every deployment to keep the schema current

For commercial licensing posture and tenant packaging, see [licensing.md](licensing.md).

