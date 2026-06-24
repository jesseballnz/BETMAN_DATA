"""
BETMAN Data API — application entrypoint.

All routes are versioned under /v1/. The WebSocket live stream
is at /v1/live/{feed_id} and requires the same API key auth.
"""

from contextlib import asynccontextmanager

import redis.asyncio as redis
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close_db_pool, create_db_pool
from app.middleware import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    TenantMiddleware,
)
from app.routers import (
    admin,
    analytics,
    assistant,
    compliance,
    discovery,
    events,
    feeds,
    health,
    intelligence,
    live,
    market,
    meetings,
    metrics,
    pedigree,
    races,
    runners,
    search,
    skins,
    stats,
    tracks,
)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("betman_api.starting", version=settings.api_version, env=settings.environment)
    app.state.db_pool = await create_db_pool()
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    yield
    log.info("betman_api.stopping")
    await close_db_pool(getattr(app.state, "db_pool", None))
    redis_client = getattr(app.state, "redis", None)
    if redis_client is not None:
        await redis_client.aclose()


app = FastAPI(
    title="BETMAN Data API",
    description=(
        "The internal data API for the BETMAN platform. "
        "Exposes races, runners, signals, commentary replay, barrier analysis, "
        "weather/track conditions, odds intelligence, and the skin engine "
        "for multi-tenant OEM licensing."
    ),
    version=settings.api_version,
    root_path=settings.api_root_path,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── Middleware (applied in reverse order — last added = outermost) ────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/v1"

app.include_router(health.router, prefix=PREFIX)
app.include_router(metrics.router, prefix=PREFIX)
app.include_router(stats.router, prefix=PREFIX)
app.include_router(meetings.router, prefix=PREFIX)
app.include_router(feeds.router, prefix=PREFIX)
app.include_router(races.router, prefix=PREFIX)
app.include_router(runners.router, prefix=PREFIX)
app.include_router(tracks.router, prefix=PREFIX)
app.include_router(events.router, prefix=PREFIX)
app.include_router(search.router, prefix=PREFIX)
app.include_router(skins.router, prefix=PREFIX)
app.include_router(intelligence.router, prefix=PREFIX)
app.include_router(pedigree.router, prefix=PREFIX)
app.include_router(market.router, prefix=PREFIX)
app.include_router(discovery.router, prefix=PREFIX)
app.include_router(analytics.router, prefix=PREFIX)
app.include_router(assistant.router, prefix=PREFIX)
app.include_router(compliance.router, prefix=PREFIX)
app.include_router(admin.router, prefix=PREFIX)
app.include_router(live.router, prefix=PREFIX)
