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

## Initial target SLOs

- API availability: **99.9% monthly**
- p95 request latency on standard read endpoints: **< 500 ms**
- readiness failure detection: **< 60 seconds**
