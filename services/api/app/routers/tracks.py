from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import fetch_all, fetch_row

router = APIRouter(prefix="/tracks", tags=["tracks", "barrier-analysis", "weather"])


class BarrierStat(BaseModel):
    barrier_number: int
    relative_barrier: str | None
    total_runners: int
    wins: int
    places: int
    win_rate: float
    place_rate: float
    avg_win_price: float | None
    rank_by_win_rate: int


class BarrierAnalysisResponse(BaseModel):
    track_name: str
    surface: str
    filters: dict
    sample_size: int
    barriers: list[BarrierStat]


class HeatmapCell(BaseModel):
    zone: str
    distance_from_finish_band: str | None
    win_rate: float
    place_rate: float
    intensity: float


class HeatmapResponse(BaseModel):
    track_name: str
    surface: str
    condition_category: str
    distance_band: str | None
    cells: list[HeatmapCell]


class SoilMoistureReading(BaseModel):
    probe_label: str
    zone: str
    moisture_pct: float
    soil_temperature_c: float | None = None


class WeatherResponse(BaseModel):
    track_name: str
    station_label: str | None
    current: dict | None
    soil_moisture: list[SoilMoistureReading]
    history: list[dict]


class ConditionReading(BaseModel):
    condition_code: str
    condition_category: str
    penetrometer_value: float | None
    recorded_at: str
    source: str


class ConditionsResponse(BaseModel):
    track_name: str
    current_condition: ConditionReading | None
    recent_readings: list[ConditionReading]


@router.get("")
async def list_tracks(request: Request):
    rows = await fetch_all(
        request,
        """
        SELECT
            track_name,
            MAX(surface) FILTER (WHERE surface IS NOT NULL) AS surface,
            MAX(race_count)::int AS race_count,
            MAX(meeting_count)::int AS meeting_count,
            MAX(barrier_sample_size)::int AS barrier_sample_size,
            MAX(heatmap_cell_count)::int AS heatmap_cell_count
        FROM (
            SELECT m.track_name, m.surface, COUNT(DISTINCT r.id) AS race_count,
                   COUNT(DISTINCT m.id) AS meeting_count, 0 AS barrier_sample_size, 0 AS heatmap_cell_count
            FROM meetings m
            LEFT JOIN races r ON r.meeting_id = m.id
            GROUP BY m.track_name, m.surface
            UNION ALL
            SELECT bo.track_name, bo.surface, 0, 0, COUNT(*) AS barrier_sample_size, 0
            FROM barrier_outcomes bo
            GROUP BY bo.track_name, bo.surface
            UNION ALL
            SELECT thc.track_name, thc.surface, 0, 0, 0, COUNT(*) AS heatmap_cell_count
            FROM track_heatmap_cells thc
            GROUP BY thc.track_name, thc.surface
        ) t
        GROUP BY track_name
        ORDER BY track_name
        """,
    )
    return {"tracks": rows}


@router.get("/{track_name}/barriers", response_model=BarrierAnalysisResponse, summary="Barrier win/place statistics")
async def get_barrier_analysis(
    request: Request,
    track_name: str,
    condition: str | None = None,
    condition_category: str | None = None,
    surface: str = "turf",
    distance_min: int | None = None,
    distance_max: int | None = None,
    race_class_group: str | None = None,
    field_size_min: int | None = None,
    since: str | None = None,
):
    clauses = ["LOWER(track_name) = LOWER($1)", "surface = $2"]
    params: list[Any] = [track_name, surface]

    if condition is not None:
        params.append(condition)
        clauses.append(f"condition_code = ${len(params)}")
    if condition_category is not None:
        params.append(condition_category)
        clauses.append(f"condition_category = ${len(params)}")
    if distance_min is not None:
        params.append(distance_min)
        clauses.append(f"distance_m >= ${len(params)}")
    if distance_max is not None:
        params.append(distance_max)
        clauses.append(f"distance_m <= ${len(params)}")
    if race_class_group is not None:
        params.append(race_class_group)
        clauses.append(f"race_class_group = ${len(params)}")
    if field_size_min is not None:
        params.append(field_size_min)
        clauses.append(f"field_size >= ${len(params)}")
    if since is not None:
        params.append(since)
        clauses.append(f"race_date >= ${len(params)}")

    rows = await fetch_all(
        request,
        f"""
        WITH aggregated AS (
            SELECT
                barrier_number,
                MAX(relative_barrier) AS relative_barrier,
                COUNT(*)::int AS total_runners,
                COUNT(*) FILTER (WHERE won)::int AS wins,
                COUNT(*) FILTER (WHERE placed)::int AS places,
                ROUND(COUNT(*) FILTER (WHERE won)::numeric * 100.0 / NULLIF(COUNT(*), 0), 2)::float AS win_rate,
                ROUND(COUNT(*) FILTER (WHERE placed)::numeric * 100.0 / NULLIF(COUNT(*), 0), 2)::float AS place_rate
            FROM barrier_outcomes
            WHERE {' AND '.join(clauses)}
            GROUP BY barrier_number
        )
        SELECT *, RANK() OVER (ORDER BY win_rate DESC, total_runners DESC, barrier_number) AS rank_by_win_rate
        FROM aggregated
        ORDER BY barrier_number
        """,
        *params,
    )

    sample_size = sum(row["total_runners"] for row in rows)
    return BarrierAnalysisResponse(
        track_name=track_name,
        surface=surface,
        filters={
            "condition_code": condition,
            "condition_category": condition_category,
            "distance_min": distance_min,
            "distance_max": distance_max,
            "race_class_group": race_class_group,
            "field_size_min": field_size_min,
            "since": since,
        },
        sample_size=sample_size,
        barriers=[BarrierStat(**{**row, "avg_win_price": None}) for row in rows],
    )


@router.get("/{track_name}/heatmap", response_model=HeatmapResponse, summary="Spatial barrier heat map")
async def get_heatmap(
    request: Request,
    track_name: str,
    condition_category: str | None = None,
    surface: str = "turf",
    distance_band: str | None = None,
):
    clauses = ["LOWER(track_name) = LOWER($1)", "surface = $2"]
    params: list[Any] = [track_name, surface]
    if condition_category is not None:
        params.append(condition_category)
        clauses.append(f"condition_category = ${len(params)}")
    if distance_band is not None:
        params.append(distance_band)
        clauses.append(f"distance_band = ${len(params)}")

    rows = await fetch_all(
        request,
        f"""
        SELECT zone, distance_from_finish_band, COALESCE(win_rate, 0)::float AS win_rate,
               COALESCE(place_rate, 0)::float AS place_rate,
               COALESCE(intensity, 0)::float AS intensity
        FROM track_heatmap_cells
        WHERE {' AND '.join(clauses)}
        ORDER BY zone, distance_from_finish_band NULLS LAST
        """,
        *params,
    )
    return HeatmapResponse(
        track_name=track_name,
        surface=surface,
        condition_category=condition_category or "all",
        distance_band=distance_band,
        cells=[HeatmapCell(**row) for row in rows],
    )


@router.get("/{track_name}/weather", response_model=WeatherResponse, summary="Live weather and soil moisture")
async def get_weather(
    request: Request,
    track_name: str,
    since: str | None = None,
    resolution: str = "raw",
):
    station = await fetch_row(
        request,
        "SELECT id, label FROM weather_stations WHERE LOWER(track_name) = LOWER($1) AND active = true ORDER BY id LIMIT 1",
        track_name,
    )
    if station is None:
        return WeatherResponse(track_name=track_name, station_label=None, current=None, soil_moisture=[], history=[])

    history_params: list[Any] = [station["id"]]
    history_clause = ""
    if since is not None:
        history_params.append(since)
        history_clause = f"AND recorded_at >= ${len(history_params)}"

    history = await fetch_all(
        request,
        f"""
        SELECT recorded_at, temperature_c, humidity_pct, rainfall_24h_mm, wind_speed_kmh
        FROM weather_readings
        WHERE station_id = $1 {history_clause}
        ORDER BY recorded_at DESC
        LIMIT 50
        """,
        *history_params,
    )
    current = history[0] if history else None
    soil = await fetch_all(
        request,
        """
        SELECT p.probe_label, p.zone, s.moisture_pct, s.soil_temperature_c
        FROM soil_moisture_probes p
        LEFT JOIN LATERAL (
            SELECT moisture_pct, soil_temperature_c
            FROM soil_moisture_readings smr
            WHERE smr.probe_id = p.id
            ORDER BY recorded_at DESC
            LIMIT 1
        ) s ON TRUE
        WHERE p.station_id = $1 AND p.active = true
        ORDER BY p.zone, p.probe_label
        """,
        station["id"],
    )
    return WeatherResponse(
        track_name=track_name,
        station_label=station["label"],
        current=current,
        soil_moisture=[SoilMoistureReading(**row) for row in soil if row["moisture_pct"] is not None],
        history=history,
    )


@router.get("/{track_name}/conditions", response_model=ConditionsResponse, summary="Track condition ratings")
async def get_conditions(request: Request, track_name: str):
    rows = await fetch_all(
        request,
        """
        SELECT tcr.condition_code, tcr.condition_category, tcr.penetrometer_value,
               tcr.recorded_at::text AS recorded_at, tcr.source
        FROM track_condition_readings tcr
        JOIN meetings m ON m.id = tcr.meeting_id
        WHERE LOWER(m.track_name) = LOWER($1)
        ORDER BY tcr.recorded_at DESC
        LIMIT 10
        """,
        track_name,
    )
    current = ConditionReading(**rows[0]) if rows else None
    return ConditionsResponse(
        track_name=track_name,
        current_condition=current,
        recent_readings=[ConditionReading(**row) for row in rows],
    )
