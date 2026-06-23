"""
Middleware for the BETMAN Data API.

TenantMiddleware:
  Resolves the Authorization: ****** header to a Tenant
  record and attaches it to request.state. All downstream route
  handlers can read request.state.tenant for the current tenant.
  Admin routes additionally require the key to have admin scope.

RequestLoggingMiddleware:
  Emits a structured log line per request including method, path,
  status code, duration, and tenant_id. Also writes a tenant_usage
  row for billing/analytics purposes.
"""

import time
import uuid
from typing import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

log = structlog.get_logger(__name__)

# Paths that do not require authentication
_PUBLIC_PATHS = {"/v1/health", "/docs", "/openapi.json", "/redoc"}
# Paths that additionally require admin scope
_ADMIN_PREFIX = "/v1/admin"


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Resolves API key → Tenant and enforces license scope.

    - Public paths: no key required
    - Standard paths: any valid active tenant key
    - Admin paths: key must have is_admin=True

    On success: sets request.state.tenant (dict with id, slug, license_type, features)
    On failure: returns 401 or 403 JSON immediately
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/docs"):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(
                {"error": "unauthorized", "message": "Missing or malformed API key"},
                status_code=401,
            )

        api_key = auth[7:]

        # Admin key shortcut (single shared key — replace with per-key DB lookup)
        if api_key == settings.admin_api_key:
            request.state.tenant = {
                "id": 0,
                "slug": "_admin",
                "license_type": "admin",
                "is_admin": True,
            }
            return await call_next(request)

        # TODO: look up api_key hash in tenant_api_keys table,
        # join to tenants, check active and license_expires_at
        tenant = await _resolve_tenant(api_key)
        if tenant is None:
            return JSONResponse(
                {"error": "unauthorized", "message": "Invalid API key"},
                status_code=401,
            )

        if not tenant.get("active"):
            return JSONResponse(
                {"error": "forbidden", "message": "Tenant account is inactive"},
                status_code=403,
            )

        if request.url.path.startswith(_ADMIN_PREFIX) and not tenant.get("is_admin"):
            return JSONResponse(
                {"error": "forbidden", "message": "Admin access required"},
                status_code=403,
            )

        request.state.tenant = tenant
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured request/response logging and usage tracking.
    Attaches a request_id to every request for log correlation.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        tenant_id = getattr(getattr(request.state, "tenant", {}), "get", lambda k, d=None: d)("id")

        log.info(
            "api.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            tenant_id=tenant_id,
        )

        response.headers["X-Request-ID"] = request_id
        return response


async def _resolve_tenant(api_key: str) -> dict | None:
    """
    Look up a tenant by API key hash.
    TODO: implement DB lookup against tenant_api_keys table.
    Returns None if key is not found or expired.
    """
    return None
