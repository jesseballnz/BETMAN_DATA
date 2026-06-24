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

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from threading import Lock

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.metrics import metrics

log = structlog.get_logger(__name__)

# Paths that do not require authentication
_PUBLIC_PATHS = {"/v1/health", "/v1/ready", "/v1/metrics", "/docs", "/openapi.json", "/redoc"}
# Paths that additionally require admin scope
_ADMIN_PREFIX = "/v1/admin"
_RATE_LIMIT_LOCK = Lock()
_RATE_LIMIT_WINDOWS: dict[tuple[int, str], dict[str, int | float]] = {}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for header, value in _security_headers().items():
            response.headers[header] = value
        return response


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

        tenant = await resolve_tenant_for_api_key(request, api_key)
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

        license_expires_at = tenant.get("license_expires_at")
        if isinstance(license_expires_at, datetime) and license_expires_at <= datetime.now(UTC):
            return JSONResponse(
                {"error": "forbidden", "message": "Tenant license has expired"},
                status_code=403,
            )

        key_expires_at = tenant.get("key_expires_at")
        if isinstance(key_expires_at, datetime) and key_expires_at <= datetime.now(UTC):
            return JSONResponse(
                {"error": "forbidden", "message": "API key has expired"},
                status_code=403,
            )

        limited, retry_after = await _rate_limit_response(request, tenant)
        if limited:
            limited.headers["Retry-After"] = str(retry_after)
            return limited

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

        metrics.observe(request.method, request.url.path, response.status_code, duration_ms)
        await _write_usage_record(request, tenant_id, response.status_code, duration_ms)
        response.headers["X-Request-ID"] = request_id
        return response


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_prefix(api_key: str) -> str:
    return api_key[:8]


async def resolve_tenant_for_api_key(request: Request, api_key: str) -> dict | None:
    """
    Look up a tenant by API key hash.
    Returns None if key is not found or expired.
    """
    if settings.admin_api_key and hmac.compare_digest(api_key, settings.admin_api_key):
        return {
            "id": 0,
            "slug": "_admin",
            "license_type": "admin",
            "license_expires_at": None,
            "active": True,
            "api_key_id": None,
            "key_prefix": api_key_prefix(api_key),
            "is_admin": True,
            "scopes": ["admin", "read", "write"],
            "requests_per_minute": settings.rate_limit_requests,
            "daily_quota": None,
        }

    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return None

    candidate_hash = hash_api_key(api_key)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                t.id,
                t.slug,
                t.license_type,
                t.license_expires_at,
                t.active,
                k.id AS api_key_id,
                k.key_hash,
                k.key_prefix,
                k.label,
                k.is_admin,
                k.active AS key_active,
                k.expires_at AS key_expires_at,
                COALESCE(k.scopes, ARRAY['read']::text[]) AS scopes,
                COALESCE(k.requests_per_minute, $2::int) AS requests_per_minute,
                k.daily_quota
            FROM tenant_api_keys k
            JOIN tenants t ON t.id = k.tenant_id
            WHERE k.key_prefix = $1
              AND k.active = true
            ORDER BY k.created_at DESC
            """,
            api_key_prefix(api_key),
            settings.rate_limit_requests,
        )
        matched: dict | None = None
        for row in rows:
            if hmac.compare_digest(candidate_hash, row["key_hash"]):
                matched = dict(row)
                if row["api_key_id"] is not None:
                    await conn.execute(
                        "UPDATE tenant_api_keys SET last_used_at = now() WHERE id = $1",
                        row["api_key_id"],
                    )
                break
        return matched


def _security_headers() -> dict[str, str]:
    headers = {
        "Content-Security-Policy": (
            "default-src 'self'; "
            "connect-src 'self' ws: wss:; "
            "img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "font-src 'self' data:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        ),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
    if settings.hsts_enabled:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


async def _rate_limit_response(request: Request, tenant: dict) -> tuple[JSONResponse | None, int]:
    tenant_id = tenant.get("id")
    if tenant_id is None:
        return None, 0

    now = time.time()
    window = settings.rate_limit_window_seconds
    limit = int(tenant.get("requests_per_minute") or settings.rate_limit_requests)
    key = (int(tenant_id), request.url.path)

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_WINDOWS.get(key)
        if bucket is None or now >= float(bucket["reset_at"]):
            bucket = {"count": 0, "reset_at": now + window}
            _RATE_LIMIT_WINDOWS[key] = bucket
        bucket["count"] = int(bucket["count"]) + 1
        count = int(bucket["count"])
        retry_after = max(1, int(float(bucket["reset_at"]) - now))

    if count > limit:
        return (
            JSONResponse(
                {"error": "rate_limited", "message": "Too many requests"},
                status_code=429,
            ),
            retry_after,
        )

    daily_quota = tenant.get("daily_quota")
    if daily_quota:
        pool = getattr(request.app.state, "db_pool", None)
        if pool is not None:
            async with pool.acquire() as conn:
                used_today = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM tenant_usage
                    WHERE tenant_id = $1
                      AND captured_at >= date_trunc('day', now())
                    """,
                    tenant_id,
                )
            if int(used_today or 0) >= int(daily_quota):
                return (
                    JSONResponse(
                        {"error": "rate_limited", "message": "Daily quota exceeded"},
                        status_code=429,
                    ),
                    window,
                )

    return None, 0


async def _write_usage_record(
    request: Request,
    tenant_id: int | None,
    status_code: int,
    duration_ms: float,
) -> None:
    if tenant_id in (None, 0):
        return
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tenant_usage (tenant_id, endpoint, method, status_code, duration_ms)
                VALUES ($1, $2, $3, $4, $5)
                """,
                tenant_id,
                request.url.path,
                request.method,
                status_code,
                int(duration_ms),
            )
    except Exception:
        log.exception("tenant_usage.write_failed", tenant_id=tenant_id, path=request.url.path)


async def write_audit_log(
    request: Request,
    *,
    action: str,
    resource: str,
    payload: dict | None = None,
) -> None:
    pool = getattr(request.app.state, "db_pool", None)
    actor_lookup = getattr(getattr(request.state, "tenant", {}), "get", lambda *_: None)
    actor = actor_lookup("key_prefix", "system")
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log (tenant_id, actor, action, resource, payload_json, ip_address)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                """,
                getattr(getattr(request.state, "tenant", {}), "get", lambda *_: None)("id"),
                actor or "system",
                action,
                resource,
                "{}" if payload is None else json.dumps(payload),
                request.client.host if request.client else None,
            )
    except Exception:
        log.exception("audit_log.write_failed", action=action, resource=resource)


def metrics_snapshot() -> str:
    return metrics.render()


def websocket_api_key_from_scope(
    authorization: str | None,
    api_key: str | None,
) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return api_key


async def _resolve_tenant(request: Request, api_key: str) -> dict | None:
    return await resolve_tenant_for_api_key(request, api_key)
