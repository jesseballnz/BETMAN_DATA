from fastapi import APIRouter, Response

from app.middleware import metrics_snapshot

router = APIRouter(tags=["health"])


@router.get("/metrics", summary="Prometheus metrics")
async def get_metrics() -> Response:
    return Response(content=metrics_snapshot(), media_type="text/plain; version=0.0.4")
