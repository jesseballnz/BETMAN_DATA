"""
Unit tests for Redis-backed rate limiting and graceful fallback.

All tests run without a live Redis instance — they use a fake async Redis.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import middleware
from app.config import settings
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_redis() -> MagicMock:
    """
    Return a minimal fake async Redis client that mimics the eval/incr/expire
    calls used by _redis_rate_limit and _redis_daily_quota.
    """
    store: dict[str, int] = {}
    ttls: dict[str, int] = {}

    async def fake_eval(script: str, num_keys: int, key: str, *args: object) -> list[int]:
        store[key] = store.get(key, 0) + 1
        window = int(args[0])
        if store[key] == 1:
            ttls[key] = window
        ttl = ttls.get(key, window)
        return [store[key], ttl]

    async def fake_incr(key: str) -> int:
        store[key] = store.get(key, 0) + 1
        return store[key]

    async def fake_expire(key: str, seconds: int) -> None:
        ttls[key] = seconds

    fake = MagicMock()
    fake.eval = fake_eval
    fake.incr = fake_incr
    fake.expire = fake_expire
    return fake


# ---------------------------------------------------------------------------
# Direct unit tests for _redis_rate_limit (sync wrappers around async fn)
# ---------------------------------------------------------------------------


def test_redis_rate_limit_allows_up_to_limit():
    async def _run():
        redis = _make_fake_redis()
        for _ in range(3):
            limited, _ = await middleware._redis_rate_limit(redis, 1, "/v1/test", limit=3, window=60)
            assert not limited

    asyncio.run(_run())


def test_redis_rate_limit_blocks_on_limit_plus_one():
    async def _run():
        redis = _make_fake_redis()
        for _ in range(3):
            await middleware._redis_rate_limit(redis, 1, "/v1/test", limit=3, window=60)
        limited, retry_after = await middleware._redis_rate_limit(redis, 1, "/v1/test", limit=3, window=60)
        assert limited
        assert retry_after >= 1

    asyncio.run(_run())


def test_redis_rate_limit_tenants_are_independent():
    async def _run():
        redis = _make_fake_redis()
        for _ in range(3):
            await middleware._redis_rate_limit(redis, tenant_id=1, path="/v1/test", limit=3, window=60)
        limited, _ = await middleware._redis_rate_limit(redis, tenant_id=2, path="/v1/test", limit=3, window=60)
        assert not limited

    asyncio.run(_run())


def test_redis_rate_limit_paths_are_independent():
    async def _run():
        redis = _make_fake_redis()
        for _ in range(3):
            await middleware._redis_rate_limit(redis, 1, "/v1/path-a", limit=3, window=60)
        limited, _ = await middleware._redis_rate_limit(redis, 1, "/v1/path-b", limit=3, window=60)
        assert not limited

    asyncio.run(_run())


def test_redis_rate_limit_new_window_resets_counter():
    """Two calls in different time-window buckets are independent."""
    async def _run():
        redis = _make_fake_redis()
        with patch.object(time, "time", return_value=0.0):
            limited, _ = await middleware._redis_rate_limit(redis, 1, "/v1/test", limit=1, window=60)
            assert not limited
        # Different bucket key → not limited
        with patch.object(time, "time", return_value=60.0):
            limited, _ = await middleware._redis_rate_limit(redis, 1, "/v1/test", limit=1, window=60)
            assert not limited

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# In-process fallback tests (HTTP-level, no live Redis required)
# ---------------------------------------------------------------------------


def test_in_process_fallback_blocks_at_limit(monkeypatch):
    """
    When Redis is absent (in-process fallback), the rate limiter still enforces
    the configured limit.
    """
    middleware._RATE_LIMIT_WINDOWS.clear()
    monkeypatch.setattr(settings, "rate_limit_requests", 1)
    client = TestClient(app)
    admin_auth = {"Authorization": "Bearer " + settings.admin_api_key}
    resp1 = client.get("/v1/stats/overview", headers=admin_auth)
    resp2 = client.get("/v1/stats/overview", headers=admin_auth)
    assert resp1.status_code == 200
    assert resp2.status_code == 429
    assert "Retry-After" in resp2.headers
