"""
TenantRouter — routes segment events based on tenant feed licensing.

When a segment arrives from Feed X, this determines which tenants are
licensed for that feed (respecting any custom override URLs and quality
preferences) and returns the list to the SegmentRouter for dispatch.

Results are cached in Redis (via StateManager) with a short TTL.
Cache is invalidated immediately when tenant feed assignments change
via the admin API (POST /admin/tenants/{id}/feeds/invalidate-cache).
"""

from dataclasses import dataclass

import structlog

from app.state import StateManager

log = structlog.get_logger(__name__)


@dataclass
class TenantFeedConfig:
    tenant_id: int
    tenant_slug: str
    feed_id: int
    override_url: str | None
    quality_preference: str


class TenantRouter:
    """
    Resolves which tenants are licensed for a given feed.

    Cache-backed by Redis with a 60-second TTL to avoid per-segment
    database hits while remaining responsive to license changes.
    """

    CACHE_TTL_S = 60

    def __init__(self, state: StateManager, db_url: str) -> None:
        self._state = state
        self._db_url = db_url

    async def get_tenants_for_feed(self, feed_id: int) -> list[TenantFeedConfig]:
        """
        Return all active tenants licensed to receive data from feed_id.
        Checks Redis cache first; falls back to a DB query on cache miss.
        """
        cached = await self._state.get_tenant_feed_cache(feed_id)
        if cached is not None:
            return [TenantFeedConfig(**row) for row in cached]

        configs = await self._query_db(feed_id)

        await self._state.set_tenant_feed_cache(
            feed_id,
            [c.__dict__ for c in configs],
            ttl=self.CACHE_TTL_S,
        )
        log.info(
            "tenant_router.cache_populated",
            feed_id=feed_id,
            tenant_count=len(configs),
        )
        return configs

    async def _query_db(self, feed_id: int) -> list[TenantFeedConfig]:
        """
        Query tenant_feeds JOIN tenants for all active, licensed tenants
        for this feed.

        TODO: implement using asyncpg / SQLAlchemy async session.
        Returns an empty list as a safe default until DB layer is wired.
        """
        return []

    async def invalidate_cache(self, feed_id: int) -> None:
        """Call this when a tenant's feed assignments change via admin API."""
        await self._state.invalidate_tenant_feed_cache(feed_id)
