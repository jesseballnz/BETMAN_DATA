"""
BETMAN AI Discovery Service — nightly pattern discovery engine.

Scans historical data every night (or on demand) to find:
  - Gate bias patterns by track/conditions
  - Trainer trends by context
  - Sire affinity shifts
  - Market anomalies
  - Heatmap performance correlations
  - Weather/ground correlations
  - Cross-layer combination signals

Results are stored in discovered_patterns and pattern_signals tables,
and surfaced via GET /v1/discovery/patterns in the API.
"""

import asyncio
import signal
import sys

import structlog

from app.config import settings
from app.discovery_engine import DiscoveryEngine

log = structlog.get_logger(__name__)

_shutdown = asyncio.Event()


def _handle_signal(sig, frame):
    log.info("betman_discovery.signal_received", sig=sig)
    _shutdown.set()


async def main():
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )

    log.info("betman_discovery.starting", env=settings.environment)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    engine = DiscoveryEngine(settings)

    try:
        await engine.run(_shutdown)
    except Exception:
        log.exception("betman_discovery.fatal_error")
        sys.exit(1)
    finally:
        log.info("betman_discovery.stopped")


if __name__ == "__main__":
    asyncio.run(main())
