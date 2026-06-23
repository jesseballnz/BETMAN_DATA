from enum import Enum
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/races", tags=["races"])


# ── Response models ───────────────────────────────────────────────────────────

class ReplayFrameType(str, Enum):
    commentary = "commentary"
    event = "event"
    odds_update = "odds_update"
    excitement_peak = "excitement_peak"


class PositionCall(BaseModel):
    position: int
    runner_name: str
    saddle_cloth: str | None = None


class ReplayFrame(BaseModel):
    offset_ms: int
    type: ReplayFrameType
    scene: str | None = None
    text: str | None = None
    event_type: str | None = None
    excitement_score: float | None = None
    thumbnail_url: str | None = None
    positions: list[PositionCall] | None = None
    # odds_update fields
    runner_name: str | None = None
    saddle_cloth: str | None = None
    win_price: float | None = None
    place_price: float | None = None
    market_status: str | None = None


class RaceReplayResponse(BaseModel):
    race_id: int
    race_name: str | None
    meeting: str | None
    race_class: str | None
    distance_m: int | None
    actual_start_time: datetime | None
    duration_ms: int | None
    replay_frames: list[ReplayFrame]


class KeyMoment(BaseModel):
    offset_ms: int
    text: str
    type: str | None = None


class RaceStoryResponse(BaseModel):
    race_id: int
    race_name: str | None
    generated_at: datetime | None
    summary: str
    key_moments: list[KeyMoment]
    winner_name: str | None
    margin_description: str | None
    model_version: str | None


class ExcitementSample(BaseModel):
    offset_ms: int
    score: float
    scene: str | None = None
    peak: bool = False


class ExcitementResponse(BaseModel):
    race_id: int
    actual_start_time: datetime | None
    samples: list[ExcitementSample]


class OddsSnapshot(BaseModel):
    captured_at: datetime
    offset_ms: int
    win_price: float | None
    place_price: float | None
    source: str


class OddsEntryDrift(BaseModel):
    race_entry_id: int
    saddle_cloth: str
    runner_name: str
    snapshots: list[OddsSnapshot]


class OddsDriftResponse(BaseModel):
    race_id: int
    actual_start_time: datetime | None
    entries: list[OddsEntryDrift]


class OddsMovementSummary(BaseModel):
    runner_name: str
    saddle_cloth: str
    movement_type: str
    from_price: float
    to_price: float
    movement_pct: float
    detected_at: datetime
    time_to_jump_s: int


class OddsEntryAnalysis(BaseModel):
    race_entry_id: int
    runner_name: str
    saddle_cloth: str
    opening_price: float | None
    closing_price: float | None
    min_price: float | None
    max_price: float | None
    total_movement_pct: float | None
    steam_detected: bool
    blowout_detected: bool
    firmings_count: int
    driftings_count: int
    biggest_move: OddsMovementSummary | None


class OddsAnalysisResponse(BaseModel):
    race_id: int
    race_name: str | None
    scheduled_start_time: datetime | None
    entries: list[OddsEntryAnalysis]
    notable_movements: list[OddsMovementSummary]


class BarrierEntry(BaseModel):
    saddle_cloth: str
    runner_name: str
    barrier_number: int
    field_size: int
    relative_barrier: str
    barrier_stats: dict | None = None


class BarrierContextResponse(BaseModel):
    race_id: int
    track_name: str | None
    condition_code: str | None
    entries: list[BarrierEntry]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", summary="List races")
async def list_races(
    date: str | None = Query(None, description="Filter by meeting date (YYYY-MM-DD)"),
    track: str | None = Query(None),
    race_class: str | None = Query(None, description="Exact class code: G1, R75, MDN"),
    race_class_group: str | None = Query(None, description="group, listed, rating_band, maiden"),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List races with optional filtering. Includes meeting and class context."""
    # TODO: query races JOIN meetings JOIN race_classes
    return {"races": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/{race_id}", summary="Get race detail")
async def get_race(race_id: int):
    """Full race detail including all entries."""
    # TODO: query race + entries + runners
    raise HTTPException(status_code=404, detail=f"Race {race_id} not found")


@router.get("/{race_id}/timeline", summary="Race timeline events")
async def get_race_timeline(race_id: int):
    """Canonical timeline events ordered by time. Includes thumbnail URLs."""
    return {"race_id": race_id, "actual_start_time": None, "events": []}


@router.get("/{race_id}/signals", summary="Raw signals for a race")
async def get_race_signals(
    race_id: int,
    type: str | None = Query(None, description="ocr, audio, scene"),
):
    """All raw signal observations (OCR, audio events, scene classifications)."""
    return {"race_id": race_id, "signals": []}


@router.get("/{race_id}/odds", summary="Odds snapshots")
async def get_race_odds(race_id: int):
    """All odds snapshots for all entries — suitable for a live odds table."""
    return {"race_id": race_id, "entries": []}


@router.get("/{race_id}/odds-drift", response_model=OddsDriftResponse, summary="Odds drift time series")
async def get_odds_drift(
    race_id: int,
    entry_id: int | None = Query(None),
):
    """Chart-ready time-series odds data per runner from market open to suspension."""
    return OddsDriftResponse(race_id=race_id, actual_start_time=None, entries=[])


@router.get("/{race_id}/odds-analysis", response_model=OddsAnalysisResponse, summary="Odds intelligence analysis")
async def get_odds_analysis(race_id: int):
    """
    Full odds movement analysis — opening/closing prices, steam detection,
    blowout detection, notable movements. Find the theory in the chaos.
    """
    return OddsAnalysisResponse(
        race_id=race_id,
        race_name=None,
        scheduled_start_time=None,
        entries=[],
        notable_movements=[],
    )


@router.get("/{race_id}/excitement", response_model=ExcitementResponse, summary="Excitement time series")
async def get_excitement(race_id: int):
    """
    Excitement score time series from pre-race to post-result.
    Render as a waveform or gradient bar behind the replay timeline.
    """
    return ExcitementResponse(race_id=race_id, actual_start_time=None, samples=[])


@router.get("/{race_id}/scene-timeline", summary="Visual scene breakdown")
async def get_scene_timeline(race_id: int):
    """Scene classification breakdown with thumbnail URLs — the visual storyboard."""
    return {"race_id": race_id, "scenes": []}


@router.get("/{race_id}/replay", response_model=RaceReplayResponse, summary="Commentary replay ⭐")
async def get_race_replay(
    race_id: int,
    from_ms: int | None = Query(None, description="Start offset ms (default: first available)"),
    to_ms: int | None = Query(None, description="End offset ms"),
    include: str = Query("commentary,events,odds,excitement", description="Comma-separated frame types"),
):
    """
    The centrepiece endpoint. Returns a unified, time-ordered stream of
    commentary, race events, position calls, and odds updates — everything
    needed to replay a race from its audio narrative alone.

    Clients step through replay_frames sequentially to reconstruct the full
    race experience as text + structured data, with no video required.
    """
    # TODO: query and merge:
    #   - transcript_segments WHERE race_id = race_id ORDER BY race_offset_ms
    #   - race_timeline_events WHERE race_id = race_id
    #   - odds_snapshots WHERE race_id = race_id (if 'odds' in include)
    #   - excitement_scores WHERE race_id = race_id (if 'excitement' in include)
    # Then merge-sort by offset_ms and return as ReplayFrame list
    return RaceReplayResponse(
        race_id=race_id,
        race_name=None,
        meeting=None,
        race_class=None,
        distance_m=None,
        actual_start_time=None,
        duration_ms=None,
        replay_frames=[],
    )


@router.get("/{race_id}/story", response_model=RaceStoryResponse, summary="AI race narrative")
async def get_race_story(race_id: int):
    """
    AI-generated prose narrative of the race, produced from transcripts
    and timeline events after the race completes.
    """
    # TODO: query race_summaries WHERE race_id = race_id
    raise HTTPException(status_code=404, detail=f"No story available for race {race_id}")


@router.get("/{race_id}/highlights", summary="Curated clip sequence")
async def get_race_highlights(race_id: int):
    """Key race moments as short clip references with thumbnails."""
    return {"race_id": race_id, "clips": []}


@router.get("/{race_id}/barrier-context", response_model=BarrierContextResponse, summary="Pre-race barrier stats")
async def get_barrier_context(race_id: int):
    """
    Each entry's drawn barrier alongside historical barrier statistics for
    this track and current condition. Ideal for pre-race analysis UI.
    """
    return BarrierContextResponse(
        race_id=race_id,
        track_name=None,
        condition_code=None,
        entries=[],
    )
