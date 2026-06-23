# BETMAN Consumer — The Nerve Centre

The Consumer is a long-running async service that orchestrates all external data ingestion
for the BETMAN platform. It is not an HTTP server — it is a persistent background process
that continuously ingests, normalises, and publishes live data.

## Responsibilities

- **HLS feed ingestion** — polls Trackside 1 and Trackside 2 HLS playlists, downloads new
  segments, stores them in MinIO, and writes metadata to Postgres.
- **Race data sync** — pulls race card and result data from external sources, writes to the
  `races`, `race_entries`, and `race_results` tables.
- **Odds ingestion** — captures every odds tick from configured bookmaker APIs, classifies
  market signals (steamers, drifters, late money), and writes to `fixed_odds_ticks` and
  `market_signals`.
- **Weather ingestion** — polls WeatherLink v2 API for every configured station and writes
  to `weather_readings` and `soil_moisture_readings`.
- **Tenant feed routing** — routes live feed segments to the correct tenants based on their
  `tenant_feeds` configuration, cached in Redis.

## Project Layout

```
services/consumer/
  app/
    main.py           — Entry point, graceful shutdown, orchestration
    config.py         — pydantic-settings configuration
    state.py          — Redis-backed live state store and pub/sub
    feed_manager.py   — HLS feed polling and segment download loops
    segment_router.py — Dispatches segments to OCR/audio queues
    tenant_router.py  — Redis-cached tenant feed licensing
    race_adapter.py   — Race data sync and barrier outcome triggers
    odds_adapter.py   — Odds tick capture and market signal classification
    weather_adapter.py— WeatherLink v2 API integration
  Dockerfile
  pyproject.toml
  .env.example
```

## Running Locally

### Prerequisites

```bash
make docker-infra
make migrate
```

### Start the Consumer

```bash
cp services/consumer/.env.example services/consumer/.env
# Edit .env — at minimum set DATABASE_URL, REDIS_URL, S3_ENDPOINT_URL

make consumer-dev
```

The Consumer will begin polling configured feeds and writing data.
Check logs with `make docker-logs-consumer`.

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `S3_ENDPOINT_URL` | MinIO or S3 endpoint |
| `S3_BUCKET` | Media storage bucket (default: `betman-media`) |
| `WEATHERLINK_API_KEY` / `WEATHERLINK_API_SECRET` | WeatherLink v2 credentials |
| `HLS_POLL_INTERVAL_S` | How often to check HLS playlists (default: 4s) |
| `ODDS_POLL_INTERVAL_S` | How often to poll odds sources (default: 10s) |

## WeatherLink Integration

The Consumer integrates with the Davis Instruments WeatherLink v2 API.
All values are converted from imperial to metric on ingestion:

- Temperature: °F → °C
- Wind speed: mph → km/h
- Pressure: inHg → hPa
- Rainfall: inches → mm

ISS (Integrated Sensor Suite) = sensor_type 37.

See `app/weather_adapter.py` for full implementation.

## Graceful Shutdown

The Consumer handles `SIGINT` and `SIGTERM` by setting an internal shutdown event,
which all internal loops check. On shutdown:
1. HLS polling stops
2. Any in-progress segment downloads complete
3. Redis connections are closed
4. The process exits cleanly

## Adding a New Adapter

1. Create `app/my_adapter.py` with an async `run(shutdown: asyncio.Event)` method.
2. Instantiate and start it in `app/main.py` via `asyncio.gather(...)`.
