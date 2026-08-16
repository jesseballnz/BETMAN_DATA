from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db import fetch_all, fetch_row

router = APIRouter(prefix="/races", tags=["races"])
MAX_ODDS_SNAPSHOTS_PER_ENTRY = 320


def _parse_date_param(value: str | None) -> date_type | None:
    if value is None:
        return None
    try:
        return date_type.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc


class ReplayFrameType(StrEnum):
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
    time_to_jump_s: int | None


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
    barrier_number: int | None
    field_size: int
    relative_barrier: str | None
    barrier_stats: dict | None = None


class BarrierContextResponse(BaseModel):
    race_id: int
    track_name: str | None
    condition_code: str | None
    entries: list[BarrierEntry]


def _build_race_filters(
    *,
    date: str | None,
    date_from: str | None,
    date_to: str | None,
    track: str | None,
    race_class: str | None,
    race_class_group: str | None,
    status: str | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    for value, clause in (
        (_parse_date_param(date), "m.meeting_date = ${idx}"),
        (_parse_date_param(date_from), "m.meeting_date >= ${idx}"),
        (_parse_date_param(date_to), "m.meeting_date <= ${idx}"),
        (track, "LOWER(m.track_name) = LOWER(${idx})"),
        (race_class, "r.race_class_code = ${idx}"),
        (race_class_group, "r.race_class_group = ${idx}"),
        (status, "r.status = ${idx}"),
    ):
        if value is not None:
            params.append(value)
            clauses.append(clause.replace("${idx}", f"${len(params)}"))

    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


@router.get("", summary="List races")
async def list_races(
    request: Request,
    date: str | None = Query(None, description="Filter by meeting date (YYYY-MM-DD)"),
    date_from: str | None = Query(None, description="Filter from meeting date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter to meeting date (YYYY-MM-DD)"),
    track: str | None = Query(None),
    race_class: str | None = Query(None, description="Exact class code: G1, R75, MDN"),
    race_class_group: str | None = Query(None, description="group, listed, rating_band, maiden"),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    where_sql, params = _build_race_filters(
        date=date,
        date_from=date_from,
        date_to=date_to,
        track=track,
        race_class=race_class,
        race_class_group=race_class_group,
        status=status,
    )
    params.extend([limit, offset])
    rows = await fetch_all(
        request,
        f"""
        SELECT
            r.id,
            r.race_number,
            r.name,
            r.distance_m,
            r.race_class_code,
            r.race_class_group,
            r.scheduled_start_time,
            r.actual_start_time,
            r.status,
            r.prize_money,
            m.id AS meeting_id,
            m.track_name,
            m.meeting_date,
            COALESCE(r.surface, m.surface) AS surface,
            m.jurisdiction,
            COUNT(*) OVER() AS total_count
        FROM races r
        JOIN meetings m ON m.id = r.meeting_id
        {where_sql}
        ORDER BY m.meeting_date DESC, m.track_name, r.race_number
        LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """,
        *params,
    )
    total = rows[0]["total_count"] if rows else 0
    races = [
        {
            "id": row["id"],
            "race_number": row["race_number"],
            "name": row["name"],
            "meeting": {
                "id": row["meeting_id"],
                "track_name": row["track_name"],
                "meeting_date": row["meeting_date"],
                "surface": row["surface"],
                "jurisdiction": row["jurisdiction"],
            },
            "distance_m": row["distance_m"],
            "race_class_code": row["race_class_code"],
            "race_class_group": row["race_class_group"],
            "scheduled_start_time": row["scheduled_start_time"],
            "actual_start_time": row["actual_start_time"],
            "status": row["status"],
            "prize_money": float(row["prize_money"]) if row["prize_money"] is not None else None,
        }
        for row in rows
    ]
    return {"races": races, "total": total, "limit": limit, "offset": offset}


@router.get("/{race_id}/analysis", summary="Get deterministic race analysis package")
async def get_race_analysis(request: Request, race_id: int):
    """Return backend-owned features and predictions for explanation clients.

    The endpoint exposes calculations already persisted by the scoring service;
    clients must not recreate probabilities, staking, or simulation locally.
    """
    race = await fetch_row(
        request,
        "SELECT id, status FROM races WHERE id = $1",
        race_id,
    )
    if not race:
        raise HTTPException(status_code=404, detail="race_not_found")
    rows = await fetch_all(
        request,
        """
        SELECT f.race_entry_id, ru.name AS runner_name, re.barrier_number,
               f.feature_version, f.generated_at, f.source_cutoff_at,
               f.feature_vector, f.provenance, f.missing_features,
               f.market_price, f.market_probability, f.model_probability,
               f.fair_odds, f.edge, f.confidence
        FROM race_analysis_features f
        JOIN race_entries re ON re.id = f.race_entry_id
        JOIN runners ru ON ru.id = f.runner_id
        WHERE f.race_id = $1
        ORDER BY f.model_probability DESC NULLS LAST, re.barrier_number NULLS LAST
        """,
        race_id,
    )
    return {
        "race_id": race_id,
        "status": race["status"],
        "calculation_authority": "betman-scoring-service",
        "probabilities_are_backend_owned": True,
        "features": [dict(row) for row in rows],
    }


@router.get("/external/{external_race_id}/analysis", summary="Get analysis by provider race id")
async def get_external_race_analysis(request: Request, external_race_id: str):
    race = await fetch_row(
        request,
        "SELECT id FROM races WHERE external_race_id = $1 LIMIT 1",
        external_race_id,
    )
    if not race:
        raise HTTPException(status_code=404, detail="race_not_found")
    return await get_race_analysis(request, race["id"])


@router.get("/external/{external_race_id}/runner-fit", summary="Get runner track and distance records")
async def get_external_runner_fit(request: Request, external_race_id: str):
    """Return exact historical runner records for the selected race context."""
    race = await fetch_row(
        request,
        "SELECT id FROM races WHERE external_race_id = $1 LIMIT 1",
        external_race_id,
    )
    if not race:
        raise HTTPException(status_code=404, detail="race_not_found")
    rows = await fetch_all(
        request,
        """
        WITH target AS (
            SELECT r.id, r.distance_m, m.track_name,
                   COALESCE((SELECT condition_category FROM track_condition_readings tcr
                             WHERE tcr.race_id = r.id OR (tcr.race_id IS NULL AND tcr.meeting_id = r.meeting_id)
                             ORDER BY (tcr.race_id = r.id) DESC, recorded_at DESC LIMIT 1), 'unknown') AS condition_category
            FROM races r JOIN meetings m ON m.id = r.meeting_id WHERE r.id = $1
        )
        SELECT ru.name AS runner_name,
               jsonb_build_object('starts', COALESCE(track.starts, 0), 'wins', COALESCE(track.wins, 0),
                                  'seconds', COALESCE(track.seconds, 0), 'thirds', COALESCE(track.thirds, 0)) AS track,
               jsonb_build_object('starts', COALESCE(distance.starts, 0), 'wins', COALESCE(distance.wins, 0),
                                  'seconds', COALESCE(distance.seconds, 0), 'thirds', COALESCE(distance.thirds, 0)) AS distance,
               jsonb_build_object('starts', COALESCE(condition.starts, 0), 'wins', COALESCE(condition.wins, 0),
                                  'seconds', COALESCE(condition.seconds, 0), 'thirds', COALESCE(condition.thirds, 0)) AS condition
        FROM target t
        JOIN race_entries current_entry ON current_entry.race_id = t.id AND NOT current_entry.scratched
        JOIN runners ru ON ru.id = current_entry.runner_id
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::int AS starts, COUNT(*) FILTER (WHERE rr.finish_position = 1)::int AS wins,
                   COUNT(*) FILTER (WHERE rr.finish_position = 2)::int AS seconds, COUNT(*) FILTER (WHERE rr.finish_position = 3)::int AS thirds
            FROM race_entries hre JOIN races hr ON hr.id = hre.race_id JOIN meetings hm ON hm.id = hr.meeting_id
            JOIN race_results rr ON rr.race_entry_id = hre.id
            WHERE hre.runner_id = current_entry.runner_id AND hr.id <> t.id AND NOT hre.scratched
              AND rr.result_quality = 'verified' AND LOWER(hm.track_name) = LOWER(t.track_name)
        ) track ON true
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::int AS starts, COUNT(*) FILTER (WHERE rr.finish_position = 1)::int AS wins,
                   COUNT(*) FILTER (WHERE rr.finish_position = 2)::int AS seconds, COUNT(*) FILTER (WHERE rr.finish_position = 3)::int AS thirds
            FROM race_entries hre JOIN races hr ON hr.id = hre.race_id
            JOIN race_results rr ON rr.race_entry_id = hre.id
            WHERE hre.runner_id = current_entry.runner_id AND hr.id <> t.id AND NOT hre.scratched
              AND rr.result_quality = 'verified' AND hr.distance_m = t.distance_m
        ) distance ON true
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::int AS starts, COUNT(*) FILTER (WHERE rr.finish_position = 1)::int AS wins,
                   COUNT(*) FILTER (WHERE rr.finish_position = 2)::int AS seconds, COUNT(*) FILTER (WHERE rr.finish_position = 3)::int AS thirds
            FROM race_entries hre JOIN races hr ON hr.id = hre.race_id
            JOIN race_results rr ON rr.race_entry_id = hre.id
            LEFT JOIN LATERAL (SELECT condition_category FROM track_condition_readings tcr
                               WHERE tcr.race_id = hr.id OR (tcr.race_id IS NULL AND tcr.meeting_id = hr.meeting_id)
                               ORDER BY (tcr.race_id = hr.id) DESC, recorded_at DESC LIMIT 1) hc ON true
            WHERE hre.runner_id = current_entry.runner_id AND hr.id <> t.id AND NOT hre.scratched
              AND rr.result_quality = 'verified' AND COALESCE(hc.condition_category, 'unknown') = t.condition_category
        ) condition ON true
        ORDER BY current_entry.barrier_number NULLS LAST, ru.name
        """,
        race["id"],
    )
    return {"race_id": race["id"], "runner_fit": [dict(row) for row in rows]}


@router.get("/{race_id}", summary="Get race detail")
async def get_race(request: Request, race_id: int):
    race = await fetch_row(
        request,
        """
        SELECT
            r.id,
            r.race_number,
            r.name,
            r.distance_m,
            r.race_class_code,
            r.race_class_group,
            rc.rank AS race_class_rank,
            r.scheduled_start_time,
            r.actual_start_time,
            r.status,
            r.prize_money,
            m.id AS meeting_id,
            m.track_name,
            m.meeting_date,
            COALESCE(r.surface, m.surface) AS surface,
            m.jurisdiction
        FROM races r
        JOIN meetings m ON m.id = r.meeting_id
        LEFT JOIN race_classes rc ON rc.id = r.race_class_id
        WHERE r.id = $1
        """,
        race_id,
    )
    if race is None:
        raise HTTPException(status_code=404, detail=f"Race {race_id} not found")

    entries = await fetch_all(
        request,
        """
        SELECT
            re.id,
            re.saddle_cloth,
            re.barrier_number,
            re.jockey_or_driver,
            re.trainer,
            re.weight_kg,
            re.scratched,
            re.final_position,
            run.id AS runner_id,
            run.name AS runner_name,
            run.type AS runner_type,
            run.country_of_origin
        FROM race_entries re
        JOIN runners run ON run.id = re.runner_id
        WHERE re.race_id = $1
        ORDER BY COALESCE(re.barrier_number, 999), COALESCE(re.saddle_cloth, '')
        """,
        race_id,
    )

    return {
        "id": race["id"],
        "race_number": race["race_number"],
        "name": race["name"],
        "meeting": {
            "id": race["meeting_id"],
            "track_name": race["track_name"],
            "meeting_date": race["meeting_date"],
            "surface": race["surface"],
            "jurisdiction": race["jurisdiction"],
        },
        "distance_m": race["distance_m"],
        "race_class_code": race["race_class_code"],
        "race_class_group": race["race_class_group"],
        "race_class_rank": race["race_class_rank"],
        "scheduled_start_time": race["scheduled_start_time"],
        "actual_start_time": race["actual_start_time"],
        "status": race["status"],
        "prize_money": float(race["prize_money"]) if race["prize_money"] is not None else None,
        "entries": [
            {
                "id": entry["id"],
                "saddle_cloth": entry["saddle_cloth"],
                "barrier_number": entry["barrier_number"],
                "runner": {
                    "id": entry["runner_id"],
                    "name": entry["runner_name"],
                    "type": entry["runner_type"],
                    "country_of_origin": entry["country_of_origin"],
                },
                "jockey_or_driver": entry["jockey_or_driver"],
                "trainer": entry["trainer"],
                "weight_kg": float(entry["weight_kg"]) if entry["weight_kg"] is not None else None,
                "scratched": entry["scratched"],
                "final_position": entry["final_position"],
            }
            for entry in entries
        ],
    }


@router.get("/{race_id}/timeline", summary="Race timeline events")
async def get_race_timeline(race_id: int):
    return {"race_id": race_id, "actual_start_time": None, "events": []}


@router.get("/{race_id}/signals", summary="Raw signals for a race")
async def get_race_signals(
    race_id: int,
    type: str | None = Query(None, description="ocr, audio, scene"),
):
    return {"race_id": race_id, "signal_type": type, "signals": []}


@router.get("/{race_id}/odds", summary="Odds snapshots")
async def get_race_odds(request: Request, race_id: int):
    race = await fetch_row(
        request,
        "SELECT id, actual_start_time, scheduled_start_time FROM races WHERE id = $1",
        race_id,
    )
    if race is None:
        raise HTTPException(status_code=404, detail=f"Race {race_id} not found")

    rows = await fetch_all(
        request,
        """
        SELECT
            re.id AS race_entry_id,
            COALESCE(re.saddle_cloth, '') AS saddle_cloth,
            run.name AS runner_name,
            os.captured_at,
            os.win_price,
            os.place_price,
            os.source
        FROM race_entries re
        JOIN runners run ON run.id = re.runner_id
        LEFT JOIN odds_snapshots os ON os.race_entry_id = re.id
        WHERE re.race_id = $1
        ORDER BY re.id, os.captured_at
        """,
        race_id,
    )
    entries = _group_odds_rows(rows, race["actual_start_time"] or race["scheduled_start_time"])
    return {
        "race_id": race_id,
        "actual_start_time": race["actual_start_time"],
        "entries": entries,
    }


@router.get(
    "/{race_id}/odds-drift", response_model=OddsDriftResponse, summary="Odds drift time series"
)
async def get_odds_drift(
    request: Request,
    race_id: int,
    entry_id: int | None = Query(None),
):
    race = await fetch_row(
        request,
        "SELECT id, actual_start_time, scheduled_start_time FROM races WHERE id = $1",
        race_id,
    )
    if race is None:
        raise HTTPException(status_code=404, detail=f"Race {race_id} not found")

    params: list[Any] = [race_id]
    entry_filter = ""
    if entry_id is not None:
        params.append(entry_id)
        entry_filter = f"AND re.id = ${len(params)}"

    rows = await fetch_all(
        request,
        f"""
        SELECT
            re.id AS race_entry_id,
            COALESCE(re.saddle_cloth, '') AS saddle_cloth,
            run.name AS runner_name,
            os.captured_at,
            os.win_price,
            os.place_price,
            os.source
        FROM race_entries re
        JOIN runners run ON run.id = re.runner_id
        LEFT JOIN odds_snapshots os ON os.race_entry_id = re.id
        WHERE re.race_id = $1 {entry_filter}
        ORDER BY re.id, os.captured_at
        """,
        *params,
    )
    entries = [
        OddsEntryDrift(**entry)
        for entry in _group_odds_rows(
            rows, race["actual_start_time"] or race["scheduled_start_time"]
        )
    ]
    return OddsDriftResponse(
        race_id=race_id, actual_start_time=race["actual_start_time"], entries=entries
    )


@router.get(
    "/{race_id}/odds-analysis",
    response_model=OddsAnalysisResponse,
    summary="Odds intelligence analysis",
)
async def get_odds_analysis(request: Request, race_id: int):
    race = await fetch_row(
        request,
        "SELECT id, name, scheduled_start_time FROM races WHERE id = $1",
        race_id,
    )
    if race is None:
        raise HTTPException(status_code=404, detail=f"Race {race_id} not found")

    rows = await fetch_all(
        request,
        """
        SELECT
            oa.race_entry_id,
            run.name AS runner_name,
            COALESCE(re.saddle_cloth, '') AS saddle_cloth,
            oa.opening_price,
            oa.closing_price,
            oa.min_price,
            oa.max_price,
            oa.total_movement_pct,
            oa.steam_detected,
            oa.blowout_detected,
            oa.firmings_count,
            oa.driftings_count,
            om.movement_type AS biggest_move_type,
            om.from_price,
            om.to_price,
            om.movement_pct,
            om.detected_at,
            om.time_to_jump_s
        FROM odds_analytics oa
        JOIN race_entries re ON re.id = oa.race_entry_id
        JOIN runners run ON run.id = re.runner_id
        LEFT JOIN LATERAL (
            SELECT movement_type, from_price, to_price, movement_pct, detected_at, time_to_jump_s
            FROM odds_movements om
            WHERE om.race_entry_id = oa.race_entry_id
            ORDER BY ABS(om.movement_pct) DESC NULLS LAST, om.detected_at DESC
            LIMIT 1
        ) om ON TRUE
        WHERE oa.race_id = $1
        ORDER BY oa.steam_detected DESC, oa.total_movement_pct ASC NULLS LAST, run.name
        """,
        race_id,
    )

    movements = await fetch_all(
        request,
        """
        SELECT
            run.name AS runner_name,
            COALESCE(re.saddle_cloth, '') AS saddle_cloth,
            om.movement_type,
            om.from_price,
            om.to_price,
            om.movement_pct,
            om.detected_at,
            om.time_to_jump_s
        FROM odds_movements om
        JOIN race_entries re ON re.id = om.race_entry_id
        JOIN runners run ON run.id = re.runner_id
        WHERE om.race_id = $1
        ORDER BY ABS(om.movement_pct) DESC, om.detected_at DESC
        LIMIT 20
        """,
        race_id,
    )

    entries: list[OddsEntryAnalysis] = []
    for row in rows:
        biggest_move = None
        if row["biggest_move_type"]:
            biggest_move = OddsMovementSummary(
                runner_name=row["runner_name"],
                saddle_cloth=row["saddle_cloth"],
                movement_type=row["biggest_move_type"],
                from_price=float(row["from_price"]),
                to_price=float(row["to_price"]),
                movement_pct=float(row["movement_pct"]),
                detected_at=row["detected_at"],
                time_to_jump_s=row["time_to_jump_s"],
            )
        entries.append(
            OddsEntryAnalysis(
                race_entry_id=row["race_entry_id"],
                runner_name=row["runner_name"],
                saddle_cloth=row["saddle_cloth"],
                opening_price=float(row["opening_price"])
                if row["opening_price"] is not None
                else None,
                closing_price=float(row["closing_price"])
                if row["closing_price"] is not None
                else None,
                min_price=float(row["min_price"]) if row["min_price"] is not None else None,
                max_price=float(row["max_price"]) if row["max_price"] is not None else None,
                total_movement_pct=row["total_movement_pct"],
                steam_detected=row["steam_detected"],
                blowout_detected=row["blowout_detected"],
                firmings_count=row["firmings_count"],
                driftings_count=row["driftings_count"],
                biggest_move=biggest_move,
            )
        )

    return OddsAnalysisResponse(
        race_id=race_id,
        race_name=race["name"],
        scheduled_start_time=race["scheduled_start_time"],
        entries=entries,
        notable_movements=[OddsMovementSummary(**_coerce_movement(row)) for row in movements],
    )


@router.get(
    "/{race_id}/excitement", response_model=ExcitementResponse, summary="Excitement time series"
)
async def get_excitement(race_id: int):
    return ExcitementResponse(race_id=race_id, actual_start_time=None, samples=[])


@router.get("/{race_id}/scene-timeline", summary="Visual scene breakdown")
async def get_scene_timeline(race_id: int):
    return {"race_id": race_id, "scenes": []}


@router.get("/{race_id}/replay", response_model=RaceReplayResponse, summary="Commentary replay ⭐")
async def get_race_replay(
    race_id: int,
    from_ms: int | None = Query(None, description="Start offset ms (default: first available)"),
    to_ms: int | None = Query(None, description="End offset ms"),
    include: str = Query(
        "commentary,events,odds,excitement", description="Comma-separated frame types"
    ),
):
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
    raise HTTPException(status_code=404, detail=f"No story available for race {race_id}")


@router.get("/{race_id}/highlights", summary="Curated clip sequence")
async def get_race_highlights(race_id: int):
    return {"race_id": race_id, "clips": []}


@router.get(
    "/{race_id}/barrier-context",
    response_model=BarrierContextResponse,
    summary="Pre-race barrier stats",
)
async def get_barrier_context(request: Request, race_id: int):
    race = await fetch_row(
        request,
        """
        SELECT r.id, m.track_name, COALESCE(r.surface, m.surface) AS surface, r.distance_m,
               tc.condition_code, tc.condition_category
        FROM races r
        JOIN meetings m ON m.id = r.meeting_id
        LEFT JOIN LATERAL (
            SELECT condition_code, condition_category
            FROM track_condition_readings tcr
            WHERE tcr.race_id = r.id OR (tcr.race_id IS NULL AND tcr.meeting_id = m.id)
            ORDER BY CASE WHEN tcr.race_id = r.id THEN 0 ELSE 1 END, recorded_at DESC
            LIMIT 1
        ) tc ON TRUE
        WHERE r.id = $1
        """,
        race_id,
    )
    if race is None:
        raise HTTPException(status_code=404, detail=f"Race {race_id} not found")

    entries = await fetch_all(
        request,
        """
        SELECT re.saddle_cloth, run.name AS runner_name, re.barrier_number,
               COUNT(*) OVER ()::int AS field_size,
               CASE
                   WHEN re.barrier_number IS NULL THEN NULL
                   WHEN re.barrier_number <= GREATEST(
                       1, CEIL(COUNT(*) OVER () / 3.0)
                   ) THEN 'inside_third'
                   WHEN re.barrier_number <= GREATEST(
                       2, CEIL((COUNT(*) OVER () * 2) / 3.0)
                   ) THEN 'middle_third'
                   ELSE 'outside_third'
               END AS relative_barrier
        FROM race_entries re
        JOIN runners run ON run.id = re.runner_id
        WHERE re.race_id = $1
        ORDER BY COALESCE(re.barrier_number, 999), COALESCE(re.saddle_cloth, '')
        """,
        race_id,
    )

    stats = await fetch_all(
        request,
        """
        SELECT barrier_number, total_runners, wins, places, win_rate, place_rate
        FROM barrier_statistics
        WHERE LOWER(track_name) = LOWER($1)
          AND surface = COALESCE($2, surface)
          AND ($3::text IS NULL OR condition_category = $3)
        ORDER BY barrier_number
        """,
        race["track_name"],
        race["surface"],
        race["condition_category"],
    )
    stat_lookup = {row["barrier_number"]: row for row in stats}

    return BarrierContextResponse(
        race_id=race_id,
        track_name=race["track_name"],
        condition_code=race["condition_code"],
        entries=[
            BarrierEntry(
                saddle_cloth=row["saddle_cloth"] or "",
                runner_name=row["runner_name"],
                barrier_number=row["barrier_number"],
                field_size=row["field_size"],
                relative_barrier=row["relative_barrier"],
                barrier_stats=stat_lookup.get(row["barrier_number"]),
            )
            for row in entries
        ],
    )


def _group_odds_rows(rows: list[dict[str, Any]], anchor: datetime | None) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        entry = grouped.setdefault(
            row["race_entry_id"],
            {
                "race_entry_id": row["race_entry_id"],
                "saddle_cloth": row["saddle_cloth"],
                "runner_name": row["runner_name"],
                "snapshots": [],
            },
        )
        if row["captured_at"] is not None:
            offset_ms = int((row["captured_at"] - anchor).total_seconds() * 1000) if anchor else 0
            entry["snapshots"].append(
                {
                    "captured_at": row["captured_at"],
                    "offset_ms": offset_ms,
                    "win_price": float(row["win_price"]) if row["win_price"] is not None else None,
                    "place_price": float(row["place_price"])
                    if row["place_price"] is not None
                    else None,
                    "source": row["source"],
                }
            )
    for entry in grouped.values():
        entry["snapshots"] = _sample_time_series(entry["snapshots"], MAX_ODDS_SNAPSHOTS_PER_ENTRY)
    return list(grouped.values())


def _sample_time_series(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(items) <= limit:
        return items
    if limit <= 2:
        return [items[0], items[-1]][:limit]
    step = (len(items) - 1) / (limit - 1)
    sampled: list[dict[str, Any]] = []
    last_index = -1
    for i in range(limit):
        index = round(i * step)
        if index <= last_index:
            index = last_index + 1
        if index >= len(items):
            index = len(items) - 1
        sampled.append(items[index])
        last_index = index
    return sampled


def _coerce_movement(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "runner_name": row["runner_name"],
        "saddle_cloth": row["saddle_cloth"],
        "movement_type": row["movement_type"],
        "from_price": float(row["from_price"]),
        "to_price": float(row["to_price"]),
        "movement_pct": float(row["movement_pct"]),
        "detected_at": row["detected_at"],
        "time_to_jump_s": row["time_to_jump_s"],
    }
