# Security policy

## Reporting a vulnerability

Please report security issues privately to the BETMAN maintainers before opening a public issue. Include:

- affected component or endpoint
- reproduction steps
- impact assessment
- any suggested mitigation

Do not post secrets, exploit payloads, or live customer data in public tickets.

## Secret-handling rules

- Never commit `.env`, `.env.*`, API keys, bearer tokens, or object-store credentials.
- Generate secrets with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- Docker Compose reads secrets from the root `.env`; `.env.example` contains placeholders only.
- The browser-facing nginx proxy must use a **read-only tenant key**, never the admin key.

## Authentication model

- API clients authenticate with `Authorization: ******
- Raw keys are shown once at creation time and stored only as deterministic PBKDF2-HMAC hashes plus a display prefix.
- Admin access requires admin-scoped keys.
- Request limits and quotas are enforced per tenant/path.

See also:

- [docs/security.md](docs/security.md)
- [docs/licensing.md](docs/licensing.md)
