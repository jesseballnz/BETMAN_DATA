"""
StateManager — Redis-backed live state for the BETMAN platform.

Tracks:
  - Feed health and current session info per feed
  - Currently live races
  - Excitement score per feed (updated by audio worker)
  - Segment processing backlog depth
  - Current weather snapshot per track
  - Tenant feed assignment cache (TTL-backed)
"""

import json
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis
import structlog

log = structlog.get_logger(__name__)

_FEED_STATE = "betman:feeds:{feed_id}:state"
_LIVE_RACES = "betman:races:live"
_EXCITEMENT = "betman:feeds:{feed_id}:excitement"
_WEATHER = "betman:tracks:{track_name}:weather"
_TENANT_FEEDS = "betman:cache:tenant_feeds:{feed_id}"


class StateManager:
    """
    Central live-state store backed by Redis.
    All Consumer components read/write platform state through here.
    The API WebSocket layer also reads from these keys to fan out to clients.
    """

    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        self._client = redis.from_url(self._url, decode_responses=True)
        await self._client.ping()
        log.info("state_manager.connected", url=self._url)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    # ------------------------------------------------------------------ feeds

    async def set_feed_state(self, feed_id: int, state: dict[str, Any]) -> None:
        key = _FEED_STATE.format(feed_id=feed_id)
        state["updated_at"] = datetime.now(UTC).isoformat()
        await self._client.set(key, json.dumps(state), ex=300)

    async def get_feed_state(self, feed_id: int) -> dict[str, Any] | None:
        raw = await self._client.get(_FEED_STATE.format(feed_id=feed_id))
        return json.loads(raw) if raw else None

    # ------------------------------------------------------------------ races

    async def add_live_race(self, race_id: int) -> None:
        await self._client.sadd(_LIVE_RACES, race_id)

    async def remove_live_race(self, race_id: int) -> None:
        await self._client.srem(_LIVE_RACES, race_id)

    async def get_live_races(self) -> set[int]:
        members = await self._client.smembers(_LIVE_RACES)
        return {int(m) for m in members}

    # --------------------------------------------------------------- excitement

    async def set_excitement(self, feed_id: int, score: float) -> None:
        await self._client.set(_EXCITEMENT.format(feed_id=feed_id), str(score), ex=60)

    async def get_excitement(self, feed_id: int) -> float:
        val = await self._client.get(_EXCITEMENT.format(feed_id=feed_id))
        return float(val) if val else 0.0

    # ----------------------------------------------------------------- weather

    async def set_weather_snapshot(
        self, track_name: str, snapshot: dict[str, Any]
    ) -> None:
        key = _WEATHER.format(track_name=track_name.lower().replace(" ", "_"))
        snapshot["updated_at"] = datetime.now(UTC).isoformat()
        await self._client.set(key, json.dumps(snapshot), ex=120)

    async def get_weather_snapshot(self, track_name: str) -> dict[str, Any] | None:
        key = _WEATHER.format(track_name=track_name.lower().replace(" ", "_"))
        raw = await self._client.get(key)
        return json.loads(raw) if raw else None

    # ---------------------------------------------------------- tenant feed cache

    async def set_tenant_feed_cache(
        self, feed_id: int, tenant_data: list[dict[str, Any]], ttl: int = 60
    ) -> None:
        key = _TENANT_FEEDS.format(feed_id=feed_id)
        await self._client.set(key, json.dumps(tenant_data), ex=ttl)

    async def get_tenant_feed_cache(
        self, feed_id: int
    ) -> list[dict[str, Any]] | None:
        key = _TENANT_FEEDS.format(feed_id=feed_id)
        raw = await self._client.get(key)
        return json.loads(raw) if raw else None

    async def invalidate_tenant_feed_cache(self, feed_id: int) -> None:
        key = _TENANT_FEEDS.format(feed_id=feed_id)
        await self._client.delete(key)
        log.info("state_manager.tenant_feed_cache_invalidated", feed_id=feed_id)

    # ------------------------------------------------------------------ pub/sub

    async def publish_event(self, channel: str, event: dict[str, Any]) -> None:
        """Publish a live event for WebSocket fanout by the API service."""
        await self._client.publish(channel, json.dumps(event))
