# Per-tenant API keys, metering, and billing

## Use case

**Who:** BETMAN platform administrators and OEM licensees.

**What:** Issue scoped tenant API keys, rotate or revoke them safely, and meter usage for billing and quota enforcement.

**Why:** The licensing model needs a direct path from product usage to monetization.

### User stories

- As an admin, I need to create a read-only webapp proxy key without exposing the admin key.
- As an operations lead, I need to rotate or revoke tenant keys without downtime.
- As finance, I need request counts by tenant and day for usage-based charging.

## Business case

- directly supports usage-based pricing and plan enforcement
- improves key hygiene for enterprise customers
- turns BETMAN_DATA’s OEM story into a measurable revenue engine

## First implementation

- `tenant_api_keys` supports scopes, per-key rate limits, and daily quotas
- tenant auth resolves hashed keys from the database with constant-time comparison
- admin endpoints create, list, rotate, and revoke tenant API keys
- `RequestLoggingMiddleware` writes `tenant_usage`
- `/v1/admin/usage` returns request summaries by tenant and day
