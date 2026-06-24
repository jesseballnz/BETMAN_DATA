"""
FeedManager — HLS stream polling and segment ingestion.

Manages all configured live HLS feeds. For each feed:
  1. Resolve the correct playlist URL (default or tenant override)
  2. Poll the media playlist at a regular interval
  3. Download new .ts segments not seen since last poll
  4. Store segments to object storage
  5. Insert a media_segments record in the DB
  6. Dispatch segment_stored events to the SegmentRouter

Tenant-specific routing (which tenants receive which segments) is
handled downstream by SegmentRouter + TenantRouter, not here.
"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime

import httpx
import structlog

from app.config import settings
from app.segment_router import SegmentRouter
from app.state import StateManager

log = structlog.get_logger(__name__)


@dataclass
class FeedConfig:
    feed_id: int
    name: str
    url: str
    poll_interval_s: float = 2.0
    quality_preference: str = "auto"


@dataclass
class Segment:
    feed_id: int
    session_id: int
    sequence_number: int
    url: str
    duration_s: float
    started_at: datetime
    ended_at: datetime
    storage_uri: str
    content_hash: str
    # Set after DB insert
    segment_id: int | None = field(default=None)


# Default feeds — loaded from DB in production; defined here as fallback
DEFAULT_FEEDS = [
    FeedConfig(
        feed_id=1,
        name="Trackside 1",
        url="https://trackside-nz.akamaized.net/hls/live/2115595/Trackside1/OnDemand/master.m3u8",
    ),
    FeedConfig(
        feed_id=2,
        name="Trackside 2",
        url="https://trackside-nz.akamaized.net/hls/live/2115596/Trackside2/OnDemand/master.m3u8",
    ),
]


class FeedManager:
    """
    Manages HLS ingestion for all configured feeds.
    Runs one async polling loop per feed, concurrently.
    """

    def __init__(
        self,
        state: StateManager,
        segment_router: SegmentRouter,
        db_url: str,
        storage_base: str,
    ) -> None:
        self._state = state
        self._router = segment_router
        self._db_url = db_url
        self._storage_base = storage_base

    async def run(self, stop_event: asyncio.Event) -> None:
        async with httpx.AsyncClient(
            timeout=settings.hls_segment_timeout_s,
            follow_redirects=True,
        ) as http:
            self._http = http
            feeds = await self._load_active_feeds()
            log.info("feed_manager.starting", feed_count=len(feeds))
            await asyncio.gather(
                *[self._poll_feed(feed, stop_event) for feed in feeds]
            )
        log.info("feed_manager.stopped")

    async def _load_active_feeds(self) -> list[FeedConfig]:
        """
        Load active feed configurations from the database.
        TODO: query feeds table; fall back to DEFAULT_FEEDS for local dev.
        """
        return DEFAULT_FEEDS

    async def _poll_feed(
        self, feed: FeedConfig, stop_event: asyncio.Event
    ) -> None:
        last_sequence: int | None = None
        session_id = await self._create_session(feed)
        log.info("feed_manager.poll_started", feed_id=feed.feed_id, name=feed.name)

        while not stop_event.is_set():
            try:
                segments, last_sequence = await self._fetch_new_segments(
                    feed, session_id, last_sequence
                )
                for segment in segments:
                    await self._store_segment(segment)
                    await self._router.dispatch(segment)

                await self._state.set_feed_state(
                    feed.feed_id,
                    {
                        "status": "active",
                        "name": feed.name,
                        "last_sequence": last_sequence,
                        "session_id": session_id,
                    },
                )
            except httpx.HTTPError:
                log.warning("feed_manager.http_error", feed_id=feed.feed_id)
                await self._state.set_feed_state(
                    feed.feed_id,
                    {"status": "error", "name": feed.name, "session_id": session_id},
                )
            except Exception:
                log.exception("feed_manager.poll_error", feed_id=feed.feed_id)

            await asyncio.sleep(feed.poll_interval_s)

        log.info("feed_manager.poll_stopped", feed_id=feed.feed_id)

    async def _create_session(self, feed: FeedConfig) -> int:
        """
        Create a new stream_sessions record in the DB.
        TODO: insert row, return generated id.
        """
        return 1  # placeholder

    async def _fetch_new_segments(
        self,
        feed: FeedConfig,
        session_id: int,
        last_sequence: int | None,
    ) -> tuple[list[Segment], int | None]:
        """
        Fetch and parse the HLS media playlist; return new segments
        with sequence numbers > last_sequence.

        TODO: use m3u8 library to parse playlist, resolve variant URL,
        diff against last_sequence.
        """
        return [], last_sequence  # placeholder

    async def _store_segment(self, segment: Segment) -> None:
        """
        Download the .ts segment bytes, upload to object storage,
        and insert a media_segments row in the DB.

        Storage path convention:
            raw/{feed_id}/{YYYY-MM-DD}/{session_id}/{sequence:08d}.ts
        """
        # TODO: httpx.get(segment.url), upload to S3, insert DB row
        pass

    @staticmethod
    def _content_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
