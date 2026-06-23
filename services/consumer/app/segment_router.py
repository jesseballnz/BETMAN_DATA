"""
SegmentRouter — dispatches stored segments to processing queues.

After a segment is stored, routes it to:
  - betman.ocr   → OCR worker (keyframe extraction + text detection)
  - betman.audio → Audio worker (VAD + classification + ASR + excitement)

The event payload includes the list of tenant IDs licensed for this
feed, so workers can scope their output (ocr_observations, audio_events,
etc.) to the correct tenants.
"""

import json

import redis.asyncio as redis
import structlog

from app.feed_manager import Segment
from app.state import StateManager
from app.tenant_router import TenantRouter

log = structlog.get_logger(__name__)


class SegmentRouter:
    def __init__(
        self,
        state: StateManager,
        queue_url: str,
        tenant_router: TenantRouter,
    ) -> None:
        self._state = state
        self._tenant_router = tenant_router
        self._queue_url = queue_url
        self._redis: redis.Redis | None = None

    async def _client(self) -> redis.Redis:
        if not self._redis:
            self._redis = redis.from_url(self._queue_url, decode_responses=True)
        return self._redis

    async def dispatch(self, segment: Segment) -> None:
        """
        Push a segment_stored event onto each processing queue.
        Includes tenant_ids so workers route output correctly.
        """
        licensed_tenants = await self._tenant_router.get_tenants_for_feed(
            segment.feed_id
        )
        tenant_ids = [t.tenant_id for t in licensed_tenants]

        event = {
            "segment_id": segment.segment_id,
            "feed_id": segment.feed_id,
            "storage_uri": segment.storage_uri,
            "started_at": segment.started_at.isoformat(),
            "ended_at": segment.ended_at.isoformat(),
            "duration_s": segment.duration_s,
            "tenant_ids": tenant_ids,
        }
        payload = json.dumps(event)

        r = await self._client()
        await r.rpush("betman.ocr", payload)
        await r.rpush("betman.audio", payload)

        # Publish to pub/sub so the API WebSocket layer can fan out
        await self._state.publish_event(
            f"betman:feed:{segment.feed_id}:segments", event
        )

        log.info(
            "segment_router.dispatched",
            feed_id=segment.feed_id,
            sequence=segment.sequence_number,
            tenant_count=len(tenant_ids),
        )
