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
- tenant keys are stored as SHA-256 hashes with a lookup prefix
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

- in-process per-tenant/path rate limiting
- optional daily quotas backed by `tenant_usage`
- structured request logs and Prometheus-style `/v1/metrics`

### Compliance and auditability

- `/v1/compliance/rules` exposes jurisdiction metadata and responsible-gambling messaging
- admin key operations write `audit_log`
- assistant responses include a “data and insights, not betting advice” disclaimer

## Operational guidance

- rotate admin and read-only proxy keys independently
- keep the proxy key scoped to `read`
- monitor `/v1/ready` and `/v1/metrics`
- review `tenant_usage` and `audit_log` as part of billing and security operations

For commercial licensing posture and tenant packaging, see [licensing.md](licensing.md).
