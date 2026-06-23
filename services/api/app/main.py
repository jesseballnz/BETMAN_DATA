"""
BETMAN Data API — application entrypoint.

All routes are versioned under /v1/. The WebSocket live stream
is at /v1/live/{feed_id} and requires the same API key auth.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware import RequestLoggingMiddleware, TenantMiddleware
from app.routers import admin, events, feeds, health, races, runners, search, skins, tracks

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("betman_api.starting", version=settings.api_version, env=settings.environment)
    # TODO: initialise DB connection pool, Redis pub/sub listener
    yield
    log.info("betman_api.stopping")
    # TODO: close DB pool, close Redis


app = FastAPI(
    title="BETMAN Data API",
    description=(
        "The internal data API for the BETMAN platform. "
        "Exposes races, runners, signals, commentary replay, barrier analysis, "
        "weather/track conditions, odds intelligence, and the skin engine "
        "for multi-tenant OEM licensing."
    ),
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── Middleware (applied in reverse order — last added = outermost) ────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(TenantMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/v1"

app.include_router(health.router,   prefix=PREFIX)
app.include_router(feeds.router,    prefix=PREFIX)
app.include_router(races.router,    prefix=PREFIX)
app.include_router(runners.router,  prefix=PREFIX)
app.include_router(tracks.router,   prefix=PREFIX)
app.include_router(events.router,   prefix=PREFIX)
app.include_router(search.router,   prefix=PREFIX)
app.include_router(skins.router,    prefix=PREFIX)
app.include_router(admin.router,    prefix=PREFIX)
