# Observability and SLO stack

## Use case

**Who:** BETMAN operators, SRE/on-call staff, and enterprise licensees evaluating readiness.

**What:** Separate liveness from readiness, expose metrics, and make privileged actions auditable.

**Why:** Licensing customers need confidence in uptime and supportability, not just features.

### User stories

- As on-call, I need honest readiness checks for Postgres and Redis.
- As platform ops, I need request counts and latency data in a scrape-friendly format.
- As a commercial lead, I need a credible SLO story for enterprise conversations.

## Business case

- strengthens the “system readiness” pillar for sales and due diligence
- reduces incident detection time
- supports future SLA-backed tiers with measurable evidence

## First implementation

- `/v1/health` and `/v1/ready` provide liveness and real dependency readiness
- `/v1/metrics` exposes Prometheus-style counters and latency buckets
- request logs include request ids and tenant ids
- admin key lifecycle changes are written to `audit_log`

## Metrics access control

`/v1/metrics` exposes per-path request counts and latency buckets.  This
telemetry is sensitive (reveals traffic patterns and error rates) so it is
**not public by default**.

| `METRICS_PUBLIC` env var | Behaviour |
|--------------------------|-----------|
| `false` (default) | Requires an admin-scoped API key |
| `true` | Accessible without authentication (use behind an internal scrape proxy) |

`/v1/health` and `/v1/ready` remain public regardless of this setting.

## Initial target SLOs

- API availability: **99.9% monthly**
- p95 request latency on standard read endpoints: **< 500 ms**
- readiness failure detection: **< 60 seconds**
