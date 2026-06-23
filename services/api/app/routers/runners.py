from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/runners", tags=["runners"])


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


@router.get("/{runner_id}", summary="Get runner detail")
async def get_runner(runner_id: int):
    """Runner detail including type and country of origin."""
    return {"runner_id": runner_id}


@router.get("/{runner_id}/form", response_model=RunnerFormResponse, summary="Runner form history")
async def get_runner_form(
    runner_id: int,
    limit: int = Query(20, le=100),
    race_class: str | None = Query(None),
):
    """
    Historical race entries for a runner with results, race class, barrier,
    track condition, and media references (replay, story, highlight clip).
    """
    return RunnerFormResponse(runner_id=runner_id, runner_name="", form=[])
