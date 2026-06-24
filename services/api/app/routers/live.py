from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.middleware import resolve_tenant_for_api_key, websocket_api_key_from_scope

router = APIRouter(tags=["feeds"])


@router.websocket("/live/{feed_id}")
async def live_feed(websocket: WebSocket, feed_id: str) -> None:
    api_key = websocket_api_key_from_scope(
        websocket.headers.get("authorization"),
        websocket.query_params.get("api_key"),
    )
    if not api_key:
        await websocket.close(code=4401, reason="Missing API key")
        return

    tenant = await resolve_tenant_for_api_key(websocket, api_key)
    if tenant is None:
        await websocket.close(code=4401, reason="Invalid API key")
        return

    await websocket.accept()
    await websocket.send_json(
        {
            "event": "connected",
            "feed_id": feed_id,
            "tenant": tenant.get("slug"),
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    redis_client = getattr(websocket.app.state, "redis", None)
    if redis_client is None:
        await _heartbeat_only(websocket, feed_id, "unavailable")
        return

    pubsub = redis_client.pubsub()
    channels = [f"betman:feeds:{feed_id}:live", "betman:races:odds", "betman:races:results"]
    await pubsub.subscribe(*channels)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("data"):
                payload = json.loads(message["data"])
                payload.setdefault("feed_id", feed_id)
                await websocket.send_json(payload)
            else:
                await websocket.send_json(
                    {
                        "event": "heartbeat",
                        "feed_id": feed_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                await asyncio.sleep(settings.websocket_heartbeat_seconds)
    except WebSocketDisconnect:
        return
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()


async def _heartbeat_only(websocket: WebSocket, feed_id: str, redis_status: str) -> None:
    try:
        while True:
            await websocket.send_json(
                {
                    "event": "heartbeat",
                    "feed_id": feed_id,
                    "redis": redis_status,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            await asyncio.sleep(settings.websocket_heartbeat_seconds)
    except WebSocketDisconnect:
        return
