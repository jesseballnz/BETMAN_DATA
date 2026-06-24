# Contributing to BETMAN_DATA

## Setup

```bash
cp .env.example .env
make setup
```

For frontend-only work:

```bash
cd services/webapp
npm install
npm run dev
```

## Before opening a PR

Run the same checks that CI runs:

```bash
python -m ruff check services/ libs/
python -m pytest tests -q

cd services/webapp
npm run lint
npm run build
```

## Security and secrets

- do not commit `.env` files or raw credentials
- generate new secrets locally
- never use the admin key as the browser proxy credential
- if you touch auth, middleware, or setup, update the matching docs

## Migrations

- add a new numbered SQL file under `infra/migrations/`
- keep migrations re-runnable
- update `make migrate`, CI, and `infra/migrations/README.md` when adding a migration

## Code style

- backend: FastAPI + asyncpg + structlog + pydantic-settings
- frontend: React 19 + Vite + Tailwind + TanStack Query
- prefer small, surgical changes that keep existing architecture intact
