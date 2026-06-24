from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import asyncpg
import structlog
from fastapi import Request

from app.config import settings

log = structlog.get_logger(__name__)


async def create_db_pool() -> asyncpg.Pool | None:
    try:
        return await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=5,
            command_timeout=10,
            statement_cache_size=0,
        )
    except Exception as exc:  # pragma: no cover - exercised in startup/manual flows
        log.warning("db.pool_unavailable", error=str(exc))
        return None


async def close_db_pool(pool: asyncpg.Pool | None) -> None:
    if pool is not None:
        await pool.close()


async def fetch_all(request: Request, query: str, *args: Any) -> list[dict[str, Any]]:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
    return [dict(row) for row in rows]


async def fetch_row(request: Request, query: str, *args: Any) -> dict[str, Any] | None:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
    return dict(row) if row else None


async def fetch_value(request: Request, query: str, *args: Any) -> Any:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return None

    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(request: Request, query: str, *args: Any) -> str | None:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return None

    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def execute_readonly_query(
    request: Request,
    query: str,
    args: Iterable[Any] = (),
    *,
    statement_timeout_ms: int = 1_500,
) -> list[dict[str, Any]]:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return []

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f"SET LOCAL statement_timeout = '{statement_timeout_ms}ms'")
            await conn.execute("SET TRANSACTION READ ONLY")
            rows = await conn.fetch(query, *list(args))
    return [dict(row) for row in rows]
