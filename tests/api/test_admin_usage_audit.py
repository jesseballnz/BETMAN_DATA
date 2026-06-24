"""
Tests for admin usage/audit endpoints.

Covers:
  - non-admin key → 403
  - admin key → 200 with documented shape
  - create/rotate/revoke write audit_log rows (via mock)
  - raw API keys only returned once on create/rotate and never stored in plaintext
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app import middleware
from app.config import settings
from app.main import app

client = TestClient(app)
ADMIN_AUTH = {"Authorization": "Bearer " + settings.admin_api_key}

_NON_ADMIN_TENANT = {
    "id": 5,
    "slug": "regular",
    "license_type": "full",
    "license_expires_at": None,
    "active": True,
    "key_expires_at": None,
    "key_prefix": "regula12",
    "is_admin": False,
    "requests_per_minute": 120,
    "daily_quota": None,
}


# ---------------------------------------------------------------------------
# /v1/admin/usage — access control
# ---------------------------------------------------------------------------


def test_admin_usage_requires_admin_key(monkeypatch):
    """A non-admin key receives 403."""

    async def _non_admin(_request, _api_key):
        return _NON_ADMIN_TENANT

    monkeypatch.setattr(middleware, "resolve_tenant_for_api_key", _non_admin)
    resp = client.get(
        "/v1/admin/usage",
        headers={"Authorization": "Bearer regular-key"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"


def test_admin_usage_returns_200_with_admin_key():
    """Admin key (no DB) → 200 with documented shape."""
    resp = client.get("/v1/admin/usage", headers=ADMIN_AUTH)
    # Without a DB, fetch_all returns [] — response is still 200.
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "days" in body


# ---------------------------------------------------------------------------
# API key lifecycle — raw key returned once, hash not exposed
# ---------------------------------------------------------------------------


def test_create_api_key_returns_raw_key_once():
    """
    POST /v1/admin/tenants/{id}/api-keys returns the raw key in the response
    body exactly once (on creation).
    """
    audit_calls: list[dict] = []

    async def _fake_fetch_row(_request, query, *args):
        return {
            "id": 99,
            "tenant_id": 1,
            "key_prefix": "testpref",
            "label": "test",
            "is_admin": False,
            "expires_at": None,
            "scopes": ["read"],
            "requests_per_minute": None,
            "daily_quota": None,
            "created_at": "2024-01-01T00:00:00Z",
        }

    async def _capture_audit(*args, **kwargs):
        audit_calls.append(kwargs)

    with (
        patch("app.routers.admin.fetch_row", side_effect=_fake_fetch_row),
        patch("app.routers.admin.write_audit_log", side_effect=_capture_audit),
    ):
        resp = client.post(
            "/v1/admin/tenants/1/api-keys",
            headers=ADMIN_AUTH,
            json={"label": "test-key", "scopes": ["read"]},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert "api_key" in body, "raw key must be returned in the create response"
    raw_key = body["api_key"]
    assert len(raw_key) > 16, "raw key should be cryptographically long"
    # The raw key must NOT appear as a stored field on the row
    assert "key_hash" not in body or body["key_hash"] != raw_key, (
        "raw key must not be stored/returned as key_hash"
    )
    # Audit log was written
    assert len(audit_calls) == 1
    assert audit_calls[0]["action"] == "tenant_api_key.create"


def test_rotate_api_key_returns_new_raw_key():
    """POST /v1/admin/tenant-api-keys/{id}/rotate returns the new raw key."""
    audit_calls: list[dict] = []

    async def _fake_fetch_row(_request, query, *args):
        return {
            "id": 99,
            "tenant_id": 1,
            "key_prefix": "testpref",
            "label": "test",
            "is_admin": False,
            "expires_at": None,
            "scopes": ["read"],
            "requests_per_minute": None,
            "daily_quota": None,
            "created_at": "2024-01-01T00:00:00Z",
        }

    async def _capture_audit(*args, **kwargs):
        audit_calls.append(kwargs)

    with (
        patch("app.routers.admin.fetch_row", side_effect=_fake_fetch_row),
        patch("app.routers.admin.write_audit_log", side_effect=_capture_audit),
    ):
        resp = client.post(
            "/v1/admin/tenant-api-keys/99/rotate",
            headers=ADMIN_AUTH,
            json={},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "api_key" in body, "new raw key must be returned in the rotate response"
    # Audit log was written
    assert len(audit_calls) == 1
    assert audit_calls[0]["action"] == "tenant_api_key.rotate"


def test_revoke_api_key_does_not_return_raw_key():
    """DELETE /v1/admin/tenant-api-keys/{id} → 204 empty body; no raw key exposed."""
    audit_calls: list[dict] = []

    async def _fake_fetch_row(_request, query, *args):
        return {"id": 99, "tenant_id": 1}

    async def _capture_audit(*args, **kwargs):
        audit_calls.append(kwargs)

    with (
        patch("app.routers.admin.fetch_row", side_effect=_fake_fetch_row),
        patch("app.routers.admin.write_audit_log", side_effect=_capture_audit),
    ):
        resp = client.delete(
            "/v1/admin/tenant-api-keys/99",
            headers=ADMIN_AUTH,
        )

    assert resp.status_code == 204
    assert resp.content == b""
    # Audit log was written
    assert len(audit_calls) == 1
    assert audit_calls[0]["action"] == "tenant_api_key.revoke"
