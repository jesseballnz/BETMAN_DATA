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

## Docker / compose

The production container builds the Vite app and serves it with nginx on port `8080`.
In `docker compose`, nginx proxies `/api/*` to the FastAPI service and injects the dev bearer token server-side so the browser bundle does not need to expose it.
