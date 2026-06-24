"""
Tests for WebSocket authentication handshake (/v1/live/{feed_id}).

Covers:
  - missing API key -> close 4401
  - invalid API key -> close 4401
  - valid API key -> accept + initial "connected" frame
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import live as live_module

client = TestClient(app)

_VALID_TENANT = {
    "id": 1,
    "slug": "test-tenant",
    "license_type": "full",
    "license_expires_at": None,
    "active": True,
    "key_expires_at": None,
    "key_prefix": "testkey1",
    "is_admin": False,
    "requests_per_minute": 120,
    "daily_quota": None,
}

# A recognisable test bearer value used in the header tests below.
_TEST_WS_BEARER = "Bearer " + "test-ws-key"


def test_websocket_missing_key_closes_4401():
    """No auth header and no api_key param -> close with code 4401."""
    with pytest.raises(Exception):
        with client.websocket_connect("/v1/live/feed-1"):
            pass  # connection should be closed immediately


def test_websocket_invalid_key_closes_4401(monkeypatch):
    """A key that resolves to None -> close with code 4401."""

    async def _null_resolver(_request, _api_key):
        return None

    # live.py imports resolve_tenant_for_api_key directly, so patch it there
    monkeypatch.setattr(live_module, "resolve_tenant_for_api_key", _null_resolver)

    with pytest.raises(Exception):
        with client.websocket_connect("/v1/live/feed-1?api_key=bad-key"):
            pass


def test_websocket_valid_key_receives_connected_frame(monkeypatch):
    """A valid query-param key -> accept + initial 'connected' JSON frame."""

    async def _good_resolver(_request, _api_key):
        return _VALID_TENANT

    monkeypatch.setattr(live_module, "resolve_tenant_for_api_key", _good_resolver)

    with client.websocket_connect("/v1/live/feed-1?api_key=test-key-abc") as ws:
        frame = ws.receive_json()
        assert frame["event"] == "connected"
        assert frame["feed_id"] == "feed-1"
        assert frame["tenant"] == "test-tenant"
        assert "timestamp" in frame


def test_websocket_valid_bearer_header_receives_connected_frame(monkeypatch):
    """A valid Authorization ****** -> accept + 'connected' frame."""

    async def _good_resolver(_request, _api_key):
        return _VALID_TENANT

    monkeypatch.setattr(live_module, "resolve_tenant_for_api_key", _good_resolver)

    with client.websocket_connect(
        "/v1/live/feed-2",
        headers={"Authorization": _TEST_WS_BEARER},
    ) as ws:
        frame = ws.receive_json()
        assert frame["event"] == "connected"
        assert frame["feed_id"] == "feed-2"
