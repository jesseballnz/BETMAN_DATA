"""
BETMAN Scoring Service — computes all 10 proprietary BETMAN scores.

This is a long-running async service that:
  1. Listens to Redis pub/sub for trigger events (race result, odds update, weather update)
  2. Computes or recomputes horse_scores for upcoming races
  3. Writes updated scores back to Postgres
  4. Publishes score updates to Redis for the API to serve in real time

Run with: python -m app.main
"""

import asyncio
import signal
import sys

import structlog

from app.config import settings
from app.score_engine import ScoreEngine

log = structlog.get_logger(__name__)

_shutdown = asyncio.Event()


def _handle_signal(sig, frame):
    log.info("betman_scoring.signal_received", sig=sig)
    _shutdown.set()


async def main():
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )

    log.info("betman_scoring.starting", env=settings.environment)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    engine = ScoreEngine(settings)

    try:
        await engine.run(_shutdown)
    except Exception:
        log.exception("betman_scoring.fatal_error")
        sys.exit(1)
    finally:
        log.info("betman_scoring.stopped")


if __name__ == "__main__":
    asyncio.run(main())
