from __future__ import annotations

from fastapi.testclient import TestClient

from app import middleware
from app.config import settings
from app.main import app

client = TestClient(app)
ADMIN_AUTH = {"Authorization": "Bearer " + settings.admin_api_key}


def test_protected_routes_require_authentication():
    response = client.get("/v1/stats/overview")
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_admin_routes_require_admin_scope(monkeypatch):
    async def fake_tenant(_request, _api_key):
        return {
            "id": 99,
            "slug": "tenant",
            "license_type": "full",
            "license_expires_at": None,
            "active": True,
            "key_expires_at": None,
            "key_prefix": "tenant12",
            "is_admin": False,
            "requests_per_minute": 10,
            "daily_quota": None,
        }

    monkeypatch.setattr(middleware, "resolve_tenant_for_api_key", fake_tenant)
    response = client.get(
        "/v1/admin/tenants", headers={"Authorization": "Bearer " + "tenant-key"}
    )
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_security_headers_are_present():
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_rate_limiter_returns_429(monkeypatch):
    middleware._RATE_LIMIT_WINDOWS.clear()
    monkeypatch.setattr(middleware.settings, "rate_limit_requests", 1)
    response_one = client.get("/v1/stats/overview", headers=ADMIN_AUTH)
    response_two = client.get("/v1/stats/overview", headers=ADMIN_AUTH)
    assert response_one.status_code == 200
    assert response_two.status_code == 429
    assert response_two.headers["Retry-After"]
