"""
BETMAN Consumer Service — the nerve centre of the BETMAN data platform.

This service is the single gateway for all live external data:
  - Trackside 1 & 2 HLS streams (and any tenant-configured custom feeds)
  - Race data feeds from external providers (TAB NZ, Racing Australia, etc.)
  - Odds and pricing feeds
  - WeatherLink weather stations + soil moisture probes

It normalises all incoming data, manages tenant feed routing (only
process data for tenants licensed for each feed), and maintains live
platform state in Redis for consumption by the API's WebSocket stream.

All other services are consumers of what this service produces.
"""

import asyncio
import signal

import structlog

from app.config import settings
from app.feed_manager import FeedManager
from app.odds_adapter import OddsAdapter
from app.race_adapter import RaceAdapter
from app.segment_router import SegmentRouter
from app.state import StateManager
from app.tenant_router import TenantRouter
from app.weather_adapter import WeatherAdapter

log = structlog.get_logger(__name__)


async def main() -> None:
    log.info("betman_consumer.starting", version=settings.version)

    state = StateManager(redis_url=settings.redis_url)
    await state.connect()

    tenant_router = TenantRouter(state=state, db_url=settings.database_url)
    segment_router = SegmentRouter(
        state=state,
        queue_url=settings.queue_url,
        tenant_router=tenant_router,
    )
    feed_manager = FeedManager(
        state=state,
        segment_router=segment_router,
        db_url=settings.database_url,
        storage_base=settings.storage_base_path,
    )
    race_adapter = RaceAdapter(state=state, db_url=settings.database_url)
    odds_adapter = OddsAdapter(state=state, db_url=settings.database_url)
    weather_adapter = WeatherAdapter(state=state, db_url=settings.database_url)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_shutdown(*_: object) -> None:
        log.info("betman_consumer.shutdown_requested")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_shutdown)

    log.info("betman_consumer.running")
    try:
        await asyncio.gather(
            feed_manager.run(stop_event),
            race_adapter.run(stop_event),
            odds_adapter.run(stop_event),
            weather_adapter.run(stop_event),
        )
    finally:
        await state.close()
        log.info("betman_consumer.stopped")


if __name__ == "__main__":
    asyncio.run(main())
