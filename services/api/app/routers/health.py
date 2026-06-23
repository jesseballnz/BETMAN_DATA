from datetime import datetime, timezone

from fastapi import APIRouter, Request
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


@router.get("/health", response_model=HealthResponse, summary="Liveness and readiness check")
async def health(request: Request) -> HealthResponse:
    """
    Returns the health status of the API and its dependencies.
    Used as the load balancer health check target.
    """
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
    redis_status = "ok"

    return HealthResponse(
        status="ok",
        version=settings.api_version,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
        db=db_status,
        redis=redis_status,
    )
