from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.db import fetch_all, fetch_row

router = APIRouter(prefix="/feeds", tags=["feeds"])


class FeedResponse(BaseModel):
    id: int
    name: str
    url: str
    active: bool
    current_session_id: int | None = None


@router.get("", summary="List all feeds")
async def list_feeds(request: Request):
    """List all configured live media feeds with current active session info."""
    rows = await fetch_all(
        request,
        """
        SELECT
            f.id,
            f.name,
            f.url,
            f.active,
            (
                SELECT ss.id
                FROM stream_sessions ss
                WHERE ss.feed_id = f.id AND ss.status = 'active'
                ORDER BY ss.started_at DESC
                LIMIT 1
            ) AS current_session_id
        FROM feeds f
        ORDER BY f.id
        """,
    )
    return {"feeds": [FeedResponse(**row).model_dump() for row in rows]}


@router.get("/{feed_id}", summary="Get feed detail")
async def get_feed(request: Request, feed_id: int):
    """Get a single feed with its current active session."""
    row = await fetch_row(
        request,
        """
        SELECT
            f.id,
            f.name,
            f.url,
            f.active,
            (
                SELECT ss.id
                FROM stream_sessions ss
                WHERE ss.feed_id = f.id AND ss.status = 'active'
                ORDER BY ss.started_at DESC
                LIMIT 1
            ) AS current_session_id
        FROM feeds f
        WHERE f.id = $1
        """,
        feed_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Feed {feed_id} not found")
    return FeedResponse(**row)
