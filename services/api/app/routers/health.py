from datetime import datetime

from fastapi import APIRouter
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
async def health() -> HealthResponse:
    """
    Returns the health status of the API and its dependencies.
    Used as the load balancer health check target.
    """
    # TODO: run actual DB ping (SELECT 1) and Redis PING
    db_status = "ok"
    redis_status = "ok"

    return HealthResponse(
        status="ok",
        version=settings.api_version,
        environment=settings.environment,
        timestamp=datetime.utcnow(),
        db=db_status,
        redis=redis_status,
    )
