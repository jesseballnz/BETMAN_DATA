from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from app.db import fetch_row

router = APIRouter(prefix="/runners", tags=["runners"])


class RunnerDetail(BaseModel):
    id: int
    name: str
    type: str | None = None
    country_of_origin: str | None = None
    external_runner_id: str | None = None


class FormEntry(BaseModel):
    race_id: int
    race_name: str | None
    race_class: str | None
    meeting_date: str | None
    track_name: str | None
    final_position: int | None
    distance_m: int | None
    condition_code: str | None
    barrier_number: int | None
    has_story: bool
    has_replay: bool
    highlight_clip_url: str | None
    thumbnail_url: str | None


class RunnerFormResponse(BaseModel):
    runner_id: int
    runner_name: str
    form: list[FormEntry]


@router.get("/{runner_id}", response_model=RunnerDetail, summary="Get runner detail")
async def get_runner(request: Request, runner_id: int):
    """Runner detail including type and country of origin."""
    row = await fetch_row(
        request,
        """
        SELECT id, name, type, country_of_origin, external_runner_id
        FROM runners
        WHERE id = $1
        """,
        runner_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Runner {runner_id} not found")
    return RunnerDetail(**row)


@router.get("/{runner_id}/form", summary="Runner form history")
async def get_runner_form(
    runner_id: int,
    limit: int = Query(20, le=100),
    race_class: str | None = Query(None),
):
    """
    Historical race entries for a runner with results, race class, barrier,
    track condition, and media references (replay, story, highlight clip).

    Not yet implemented — media/story pipeline linkage is pending.
    """
    return Response(
        status_code=501,
        content='{"detail":"Runner form history is not yet implemented"}',
        media_type="application/json",
    )
