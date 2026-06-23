# BETMAN_DATA — Deployment Guide

This guide covers everything needed to run BETMAN_DATA locally, on staging, and in production.

---

## Architecture Overview

BETMAN_DATA is composed of the following deployable units:

| Service | Role | Replicas (prod) |
|---|---|---|
| `services/api` | FastAPI internal API — query layer | 2–4 (stateless, HPA) |
| `services/consumer` | Nerve centre — live feed + data ingestion | 1 (stateful, leader election future) |
| `services/ocr-worker` | Keyframe extraction + OCR | 1–N (queue-driven) |
| `services/audio-worker` | Audio classification + ASR | 1–N (queue-driven) |
| PostgreSQL (+ pgvector) | Operational warehouse | 1 primary + 1 read replica |
| Redis | Live state + task queue + pub/sub | 1 (cluster in prod) |
| Object storage | Raw segments, clips, assets | Managed (S3 / MinIO) |

**Startup order (hard dependencies):**
```
PostgreSQL → Redis → [run migrations] → Consumer → API → Workers
```

---

## 1. Local Development

### Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Docker + Docker Compose | 24.x / 2.x | https://docs.docker.com/get-docker/ |
| Python | 3.11+ | https://python.org |
| `make` | any | included on macOS/Linux |
| `psql` (optional) | 15+ | for manual DB access |

### Quick start (Docker Compose)

This is the fastest way to get everything running locally. All services, including PostgreSQL, Redis, and MinIO (S3-compatible object storage), start in containers.

```bash
# 1. Clone the repository
git clone https://github.com/jesseballnz/BETMAN_DATA.git
cd BETMAN_DATA

# 2. Copy environment files
cp services/api/.env.example services/api/.env
cp services/consumer/.env.example services/consumer/.env

# 3. Start all infrastructure + services
make docker-up

# 4. Apply database migrations (first run only)
make migrate

# 5. Verify everything is healthy
make status
```

The API will be available at:
- **API:** http://localhost:8000
- **API docs (Swagger):** http://localhost:8000/docs
- **MinIO console:** http://localhost:9001 (user: `betman`, password: `betman_secret`)

### Running services individually (without Docker)

If you prefer to run Python services directly (e.g., for faster iteration on the API):

```bash
# Start infrastructure only
make docker-infra

# In a separate terminal — API
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # edit DATABASE_URL etc.
uvicorn app.main:app --reload --port 8000

# In another terminal — Consumer
cd services/consumer
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m app.main
```

### Applying migrations

```bash
# Against local Docker Compose Postgres
make migrate

# Against any Postgres instance
DATABASE_URL="******localhost:5432/betman" make migrate

# Manually with psql
psql $DATABASE_URL -f infra/migrations/001_initial_schema.sql
```

---

## 2. Environment Variables

### `services/api/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `REDIS_URL` | ✅ | — | Redis URL for pub/sub and live state |
| `API_VERSION` | | `1.0.0` | Reported in `/health` response |
| `MEDIA_BASE_URL` | ✅ | — | Base URL for object storage (e.g. `https://s3.ap-southeast-2.amazonaws.com/betman-media`) |
| `CDN_BASE_URL` | ✅ | — | Public CDN URL for tenant assets (e.g. `https://cdn.betman.io`) |
| `ADMIN_API_KEY` | ✅ | — | Master API key for `/admin/` routes |
| `PLATFORM_MASTER_KEY` | ✅ | — | AES-256 key for decrypting `api_key_configs.encrypted_key` |
| `CORS_ORIGINS` | | `*` | Comma-separated allowed CORS origins |
| `LOG_LEVEL` | | `info` | `debug`, `info`, `warning`, `error` |
| `ENVIRONMENT` | | `development` | `development`, `staging`, `production` |

### `services/consumer/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `REDIS_URL` | ✅ | — | Redis URL for live state |
| `QUEUE_URL` | ✅ | — | Redis URL for task queue (can be same instance, different DB) |
| `STORAGE_BASE_PATH` | ✅ | — | Object storage path (e.g. `s3://betman-media`) |
| `STORAGE_REGION` | | `ap-southeast-2` | AWS region for S3 |
| `HLS_POLL_INTERVAL_S` | | `2.0` | HLS playlist poll frequency |
| `ODDS_POLL_INTERVAL_S` | | `10.0` | Odds feed poll frequency |
| `WEATHERLINK_POLL_INTERVAL_S` | | `60.0` | WeatherLink API poll frequency |
| `WEATHERLINK_BASE_URL` | | `https://api.weatherlink.com/v2` | WeatherLink API base URL |
| `ODDS_STEAM_THRESHOLD_PCT` | | `20.0` | % firming to classify as steam |
| `ODDS_BLOWOUT_THRESHOLD_PCT` | | `20.0` | % drifting to classify as blowout |
| `PLATFORM_MASTER_KEY` | ✅ | — | AES-256 key for decrypting external API keys |
| `LOG_LEVEL` | | `info` | |
| `ENVIRONMENT` | | `development` | |

---

## 3. Docker Compose Reference

The `docker-compose.yml` at the repository root brings up the full local stack.

```bash
# Start everything
docker compose up -d

# Start infrastructure only (Postgres, Redis, MinIO) — run Python services natively
docker compose up -d postgres redis minio

# View logs for a specific service
docker compose logs -f consumer
docker compose logs -f api

# Restart a single service after a code change
docker compose restart api

# Stop and remove all containers (data volumes preserved)
docker compose down

# Stop and remove containers AND volumes (full reset)
docker compose down -v
```

### Creating the MinIO bucket (first run)

```bash
# Connect to MinIO and create the media bucket
docker compose exec minio mc alias set local http://localhost:9000 betman betman_secret
docker compose exec minio mc mb local/betman-media
docker compose exec minio mc anonymous set download local/betman-media
```

---

## 4. Production Deployment

### Recommended cloud stack (AWS)

| Component | AWS Service | Notes |
|---|---|---|
| API service | ECS Fargate (or EKS) | Stateless — 2+ replicas behind ALB |
| Consumer service | ECS Fargate — single task | Single instance; leader election for future HA |
| OCR worker | ECS Fargate | Scaled by queue depth (SQS/Redis queue) |
| Audio worker | ECS Fargate | Scaled by queue depth |
| PostgreSQL | RDS PostgreSQL 16 + pgvector extension | Multi-AZ, automated backups |
| Redis | ElastiCache Redis 7 | Cluster mode for pub/sub volume |
| Object storage | S3 | `betman-media` bucket, CloudFront CDN in front |
| Secrets | AWS Secrets Manager | All `.env` secrets injected at runtime |
| Container registry | ECR | One repo per service |
| Load balancer | ALB | HTTPS termination, path-based routing |
| DNS | Route 53 | `data-api.betman.internal` or public domain |

### Building and pushing images

```bash
# Build all service images
make docker-build

# Tag and push to ECR (replace ACCOUNT_ID and REGION)
ACCOUNT_ID=123456789012
REGION=ap-southeast-2
REGISTRY=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $REGISTRY

docker tag betman-api:latest $REGISTRY/betman-api:latest
docker push $REGISTRY/betman-api:latest

docker tag betman-consumer:latest $REGISTRY/betman-consumer:latest
docker push $REGISTRY/betman-consumer:latest
```

### Production environment variables

Never put secrets in source control. Use your cloud provider's secret management:

```bash
# AWS Secrets Manager — create secrets per service
aws secretsmanager create-secret \
  --name betman/api/production \
  --secret-string '{
    "DATABASE_URL": "******rds-host:5432/betman",
    "REDIS_URL": "redis://elasticache-host:6379/0",
    "ADMIN_API_KEY": "...",
    "PLATFORM_MASTER_KEY": "..."
  }'
```

Inject secrets into ECS task definitions via `secrets:` references — never as plaintext environment variables.

### Running migrations in production

Migrations should be applied as a one-off task before deploying new service versions:

```bash
# Run migration as a one-off ECS task (example)
aws ecs run-task \
  --cluster betman-prod \
  --task-definition betman-migrate \
  --overrides '{"containerOverrides": [{"name": "migrate", "command": ["psql", "$DATABASE_URL", "-f", "infra/migrations/001_initial_schema.sql"]}]}'

# Or via a CI/CD pipeline step:
make migrate DATABASE_URL=$PROD_DATABASE_URL
```

**Migration strategy:**
- Migrations are numbered sequentially: `001_`, `002_`, etc.
- Each migration is idempotent (uses `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`)
- Never modify an existing migration file — add a new numbered file for schema changes
- Apply migrations before deploying new service code that depends on them

### pgvector extension

The `pgvector` extension must be enabled on the RDS instance before running migrations:

```bash
# On RDS, connect as superuser and run:
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Verify
psql $DATABASE_URL -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

On AWS RDS, `pgvector` is available in PostgreSQL 15.2+ — enable it via the console or parameter group.

---

## 5. Health Checks

### API health check

```bash
curl http://localhost:8000/v1/health
# {"status": "ok", "version": "1.0.0", "timestamp": "...", "db": "ok", "redis": "ok"}
```

The health endpoint checks both PostgreSQL and Redis connectivity. Use this as your load balancer health check target.

**ALB / ECS health check config:**
```
Path: /v1/health
Port: 8000
Protocol: HTTP
Healthy threshold: 2
Unhealthy threshold: 3
Interval: 30s
Timeout: 5s
```

### Consumer health check

The Consumer does not expose an HTTP port by default. Monitor it via:
- Redis key `betman:feeds:*:state` — should have `status: "active"` and a recent `updated_at`
- CloudWatch / Datadog metrics on the ECS task
- Dead-letter queue depth on the processing queues

```bash
# Check feed health via Redis CLI
redis-cli get "betman:feeds:1:state"
redis-cli get "betman:feeds:2:state"
```

---

## 6. Monitoring & Observability

### Structured logging

All services emit structured JSON logs via `structlog`. Key fields on every log line:

```json
{
  "timestamp": "2024-03-09T03:32:05.123Z",
  "level": "info",
  "event": "segment_router.dispatched",
  "feed_id": 1,
  "tenant_count": 3,
  "service": "consumer",
  "version": "1.0.0",
  "environment": "production"
}
```

Ship logs to your log aggregator (CloudWatch Logs, Datadog, Loki).

### Key metrics to alert on

| Metric | Threshold | Action |
|---|---|---|
| API p99 latency | > 500ms | Scale API replicas |
| API 5xx error rate | > 1% | Page on-call |
| Consumer feed error | > 3 consecutive polls | Page on-call |
| Processing queue depth | > 500 | Scale workers |
| DB connection pool saturation | > 90% | Scale DB or connection pool |
| Redis memory usage | > 80% | Increase instance or flush stale keys |

### Recommended dashboards

1. **Live platform status** — feed health, live races, excitement levels, segment throughput
2. **API performance** — request rate, p50/p95/p99 latency, error rate per endpoint
3. **Processing pipeline** — queue depth, OCR throughput, audio classification rate
4. **Tenant usage** — API calls per tenant, data consumed, active skin resolutions
5. **Odds intelligence** — steam/blowout events detected, odds snapshot rate
6. **Weather & conditions** — soil moisture per probe, temperature, track condition timeline

---

## 7. Scaling Guide

### API service

The API is stateless — scale horizontally behind a load balancer.

```bash
# ECS — update desired count
aws ecs update-service \
  --cluster betman-prod \
  --service betman-api \
  --desired-count 4
```

Set up auto-scaling on CPU > 60% or request count per target.

### Consumer service

The Consumer is currently designed as a single instance. It manages HLS polling loops concurrently within one async process. For HA in future:
- Use Redis-based leader election (e.g., `redis-py-lock`) so only one instance polls a given feed
- Run 2 instances with different feed assignments as a manual partition

### Workers (OCR, audio)

Workers are queue-driven and horizontally scalable:
- Scale based on Redis queue depth
- Each worker processes one segment at a time
- Add replicas to increase parallelism

---

## 8. Backup & Recovery

### PostgreSQL

- Enable automated RDS backups (7–35 day retention)
- Point-in-time recovery enabled by default on RDS Multi-AZ
- For manual backup: `pg_dump $DATABASE_URL > betman-$(date +%Y%m%d).sql`

### Redis

- ElastiCache AOF persistence enabled for pub/sub state durability
- Redis state is reconstructable from PostgreSQL — a Consumer restart will repopulate live state within seconds

### Object storage (S3)

- Enable S3 versioning on the `betman-media` bucket
- Enable S3 lifecycle rules for raw segment tiering:
  - `raw/` prefix → Glacier after 14 days
  - `clips/` prefix → Standard-IA after 90 days
  - `frames/` prefix → Standard-IA after 30 days

---

## 9. Upgrading

### Rolling API deployment (zero downtime)

```bash
# 1. Build and push new image
make docker-build
docker push $REGISTRY/betman-api:v1.2.0

# 2. Apply any new migrations first
make migrate DATABASE_URL=$PROD_DATABASE_URL

# 3. Update ECS service — ECS will do a rolling deployment
aws ecs update-service \
  --cluster betman-prod \
  --service betman-api \
  --force-new-deployment
```

### Consumer upgrade

The Consumer maintains stateful polling loops. To upgrade with minimal feed gap:

```bash
# 1. Apply migrations
# 2. Start new consumer instance — it will begin polling immediately
# 3. Stop old consumer instance
# There will be a brief overlap in polling, which is safe (segments are idempotent on content_hash)
```

---

## 10. Troubleshooting

### Feed not ingesting

```bash
# Check Consumer logs
docker compose logs -f consumer

# Check feed state in Redis
redis-cli get "betman:feeds:1:state"

# Manually test the HLS playlist URL
curl -I "https://trackside-nz.akamaized.net/hls/live/2115595/Trackside1/OnDemand/master.m3u8"
```

### API returning 500 errors

```bash
# Check API logs
docker compose logs -f api

# Check DB connectivity
psql $DATABASE_URL -c "SELECT 1;"

# Check Redis
redis-cli -u $REDIS_URL ping
```

### Migration fails

```bash
# Check if pgvector is installed
psql $DATABASE_URL -c "SELECT extname FROM pg_extension;"

# Install if missing
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Re-run migration
psql $DATABASE_URL -f infra/migrations/001_initial_schema.sql
```

### WeatherLink not receiving data

```bash
# Check API key config in DB
psql $DATABASE_URL -c "SELECT id, service_name, key_name, active FROM api_key_configs WHERE service_name = 'weatherlink';"

# Test WeatherLink connectivity via admin API
curl -X POST http://localhost:8000/v1/admin/api-keys/1/test \
  -H "Authorization: ******"
```

### Tenant skin not resolving

```bash
# Check tenant is active
psql $DATABASE_URL -c "SELECT id, slug, active, license_expires_at FROM tenants WHERE slug = 'ladbrokes';"

# Check skin is set as default
psql $DATABASE_URL -c "SELECT id, name, is_default, active FROM skins WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'ladbrokes');"

# Test skin resolution
curl "http://localhost:8000/v1/skins/ladbrokes"
```
