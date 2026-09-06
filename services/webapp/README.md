# BETMAN Data Viewer

React + TypeScript + Vite frontend for the BETMAN_DATA warehouse console.

## Stack
- React 19 + TypeScript + Vite
- Tailwind CSS
- TanStack Query polling
- AG Grid community
- Apache ECharts

## Local development

```bash
cd services/webapp
npm install
npm run dev
```

Environment variables:
- `VITE_API_BASE_URL` — defaults to `http://localhost:8000/v1`
- `VITE_API_BEARER_TOKEN` — optional bearer token for direct API access outside docker-compose

## Native viewer authentication

`server.cjs` delegates username/password validation to BETMAN Core's `/api/login` endpoint.

- `BETMAN_CORE_ORIGIN` — the environment-local BETMAN Core origin
- `BETMAN_DATA_ADMIN_USER` — the sole Data admin username; defaults to `betman`
- `BETMAN_DATA_AUTH_SECRET` — HMAC secret for Data viewer sessions
- `BETMAN_DATA_AUTH_TOKEN_TTL_MS` — session lifetime in milliseconds
- `API_PROXY_AUTHORIZATION` — preferred read-only upstream bearer header for customer users
- `API_ADMIN_PROXY_AUTHORIZATION` — optional admin upstream bearer header; defaults to `ADMIN_API_KEY`

Every valid Core user can sign in. The configured BETMAN admin can access all proxied API routes. Other users are restricted to read routes plus `POST /v1/assistant/query`, whose database executor is read-only; admin and mutation requests return `403 betman_data_read_only`. If a read-only upstream bearer is not configured, the native proxy falls back to the server-side admin bearer only after applying those read-only route restrictions.

## Docker / compose

The production container builds the Vite app and serves it with nginx on port `8080`.
In `docker compose`, nginx proxies `/api/*` and `/api/v1/live/*` to the FastAPI service and injects a **read-only tenant bearer token** server-side so the browser bundle does not need to expose it. Never use the admin key as the proxy credential.
