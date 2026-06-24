from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime
    db: str
    redis: str


async def _dependency_statuses(request: Request) -> tuple[str, str]:
    pool = getattr(request.app.state, "db_pool", None)
    db_status = "ok"
    if pool is None:
        db_status = "unavailable"
    else:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception:
            db_status = "error"

    redis_client = getattr(request.app.state, "redis", None)
    redis_status = "ok"
    if redis_client is None:
        redis_status = "unavailable"
    else:
        try:
            await redis_client.ping()
        except Exception:
            redis_status = "error"

    return db_status, redis_status


@router.get("/health", response_model=HealthResponse, summary="Service liveness check")
async def health(request: Request) -> HealthResponse:
    """
    Returns the health status of the API and its dependencies.
    Used as the load balancer health check target.
    """
    db_status, redis_status = await _dependency_statuses(request)

    return HealthResponse(
        status="ok",
        version=settings.api_version,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
        db=db_status,
        redis=redis_status,
    )


@router.get("/ready", response_model=HealthResponse, summary="Dependency readiness check")
async def ready(request: Request, response: Response) -> HealthResponse:
    db_status, redis_status = await _dependency_statuses(request)
    ready_status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    if ready_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=ready_status,
        version=settings.api_version,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
        db=db_status,
        redis=redis_status,
    )
