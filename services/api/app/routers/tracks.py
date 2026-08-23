from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import fetch_all, fetch_row

router = APIRouter(prefix="/tracks", tags=["tracks", "barrier-analysis", "weather"])

TRACK_ALIASES = {
    "ballarat": "Sportsbet-Ballarat",
    "ballarat synthetic": "Sportsbet-Ballarat Synthetic",
    "beaudesert": "Aquis Beaudesert",
    "canterbury": "Canterbury Park",
    "devonport synthetic": "Devonport Tapeta",
    "echuca": "bet365 Echuca",
    "geelong": "bet365 Geelong",
    "gold coast": "Aquis Park Gold Coast",
    "mildura": "bet365 Mildura",
    "pakenham synthetic": "Sportsbet-Pakenham Synthetic",
    "randwick": "Royal Randwick",
    "rosehill": "Rosehill Gardens",
    "sandown": "Sportsbet Sandown",
    "wangaratta": "Sportsbet-Wangaratta",
    "wodonga": "bet365 Park Wodonga",
}


def canonical_track_name(value: str) -> str:
    display_name = " ".join(str(value or "").strip().split())
    return TRACK_ALIASES.get(display_name.lower(), display_name)


def parse_since(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="since must be YYYY-MM-DD") from exc

SURFACE_CONTEXT_SQL = """
CASE lower(NULLIF({column}, ''))
    WHEN 'grass' THEN 'turf'
    WHEN 'turf' THEN 'turf'
    WHEN 'synthetic' THEN 'synthetic'
    WHEN 'dirt' THEN 'dirt'
    ELSE COALESCE(NULLIF({column}, ''), 'unknown')
END
"""

RELATIVE_BARRIER_ZONE_SQL = """
CASE lower(COALESCE({column}, ''))
    WHEN 'inside_third' THEN 'inside'
    WHEN 'middle_third' THEN 'middle'
    WHEN 'outside_third' THEN 'outside'
    ELSE 'unknown'
END
"""

DISTANCE_BAND_SQL = """
CASE
    WHEN {column} IS NULL THEN 'all'
    WHEN {column} <= 1200 THEN 'sprint'
    WHEN {column} <= 1600 THEN 'mile'
    ELSE 'staying'
END
"""


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
    sample_races: int = 0
    sample_date_from: str | None = None
    sample_date_to: str | None = None
    barriers: list[BarrierStat]


class HeatmapCell(BaseModel):
    zone: str
    distance_band: str | None = None
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
        f"""
        SELECT
            track_name,
            surface,
            SUM(race_count)::int AS race_count,
            SUM(meeting_count)::int AS meeting_count,
            SUM(barrier_sample_size)::int AS barrier_sample_size,
            GREATEST(
                SUM(heatmap_cell_count),
                SUM(derived_heatmap_cell_count)
            )::int AS heatmap_cell_count
        FROM (
            SELECT
                m.track_name,
                {SURFACE_CONTEXT_SQL.format(column="m.surface")} AS surface,
                COUNT(DISTINCT r.id) AS race_count,
                COUNT(DISTINCT m.id) AS meeting_count,
                0 AS barrier_sample_size,
                0 AS heatmap_cell_count,
                0 AS derived_heatmap_cell_count
            FROM meetings m
            LEFT JOIN races r ON r.meeting_id = m.id
            GROUP BY m.track_name, {SURFACE_CONTEXT_SQL.format(column="m.surface")}
            UNION ALL
            SELECT
                bo.track_name,
                {SURFACE_CONTEXT_SQL.format(column="bo.surface")} AS surface,
                0,
                0,
                COUNT(*) AS barrier_sample_size,
                0,
                COUNT(DISTINCT CONCAT_WS(
                    '|',
                    {RELATIVE_BARRIER_ZONE_SQL.format(column="bo.relative_barrier")},
                    {DISTANCE_BAND_SQL.format(column="bo.distance_m")}
                )) AS derived_heatmap_cell_count
            FROM barrier_outcomes bo
            GROUP BY bo.track_name, {SURFACE_CONTEXT_SQL.format(column="bo.surface")}
            UNION ALL
            SELECT
                thc.track_name,
                {SURFACE_CONTEXT_SQL.format(column="thc.surface")} AS surface,
                0,
                0,
                0,
                COUNT(*) AS heatmap_cell_count,
                0
            FROM track_heatmap_cells thc
            GROUP BY thc.track_name, {SURFACE_CONTEXT_SQL.format(column="thc.surface")}
        ) t
        GROUP BY track_name, surface
        ORDER BY track_name, surface
        """,
    )
    return {"tracks": rows}


@router.get(
    "/{track_name}/barriers",
    response_model=BarrierAnalysisResponse,
    summary="Barrier win/place statistics",
)
async def get_barrier_analysis(
    request: Request,
    track_name: str,
    condition: str | None = None,
    condition_category: str | None = None,
    surface: str = "all",
    distance_min: int | None = None,
    distance_max: int | None = None,
    race_class_group: str | None = None,
    field_size_min: int | None = None,
    since: str | None = None,
):
    query_track = canonical_track_name(track_name)
    clauses = ["LOWER(track_name) = LOWER($1)"]
    params: list[Any] = [query_track]

    if surface != "all":
        params.append(surface)
        clauses.append(
            f"LOWER({SURFACE_CONTEXT_SQL.format(column='surface')}) = LOWER(${len(params)})"
        )

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
        params.append(parse_since(since))
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
                ROUND(
                    COUNT(*) FILTER (WHERE won)::numeric * 100.0 / NULLIF(COUNT(*), 0),
                    2
                )::float AS win_rate,
                ROUND(
                    COUNT(*) FILTER (WHERE placed)::numeric * 100.0 / NULLIF(COUNT(*), 0),
                    2
                )::float AS place_rate
            FROM barrier_outcomes
            WHERE {" AND ".join(clauses)}
            GROUP BY barrier_number
        )
        SELECT *,
               RANK() OVER (
                   ORDER BY win_rate DESC, total_runners DESC, barrier_number
               ) AS rank_by_win_rate
        FROM aggregated
        ORDER BY barrier_number
        """,
        *params,
    )

    sample_size = sum(row["total_runners"] for row in rows)
    metadata = await fetch_row(
        request,
        f"""
        SELECT COUNT(DISTINCT race_id)::int AS sample_races,
               MIN(race_date)::text AS sample_date_from,
               MAX(race_date)::text AS sample_date_to
        FROM barrier_outcomes
        WHERE {" AND ".join(clauses)}
        """,
        *params,
    )
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
        sample_races=int((metadata or {}).get("sample_races") or 0),
        sample_date_from=(metadata or {}).get("sample_date_from"),
        sample_date_to=(metadata or {}).get("sample_date_to"),
        barriers=[BarrierStat(**{**row, "avg_win_price": None}) for row in rows],
    )


@router.get(
    "/{track_name}/heatmap", response_model=HeatmapResponse, summary="Spatial barrier heat map"
)
async def get_heatmap(
    request: Request,
    track_name: str,
    condition_category: str | None = None,
    surface: str = "all",
    distance_band: str | None = None,
):
    query_track = canonical_track_name(track_name)
    cell_clauses = ["LOWER(track_name) = LOWER($1)"]
    outcome_clauses = ["LOWER(track_name) = LOWER($1)"]
    params: list[Any] = [query_track]

    if surface != "all":
        params.append(surface)
        surface_clause = (
            f"LOWER({SURFACE_CONTEXT_SQL.format(column='surface')}) = LOWER(${len(params)})"
        )
        cell_clauses.append(surface_clause)
        outcome_clauses.append(surface_clause)
    if condition_category is not None:
        params.append(condition_category)
        condition_clause = f"condition_category = ${len(params)}"
        cell_clauses.append(condition_clause)
        outcome_clauses.append(condition_clause)
    if distance_band is not None:
        # Core labels 1,201–1,600m as ``middle`` while older warehouse
        # records use the canonical stored label ``mile``.
        distance_value = "mile" if str(distance_band).strip().lower() == "middle" else distance_band
        params.append(distance_value)
        cell_clauses.append(f"distance_band = ${len(params)}")
        outcome_clauses.append(
            f"{DISTANCE_BAND_SQL.format(column='distance_m')} = ${len(params)}"
        )

    rows = await fetch_all(
        request,
        f"""
        WITH grouped AS (
            -- A stored cell exists per condition slice. The UI needs one
            -- comparable Inside/Middle/Outside cell per distance band, so
            -- combine those slices using their underlying runner counts.
            SELECT
                zone,
                distance_band,
                SUM(win_count)::int AS win_count,
                SUM(place_count)::int AS place_count,
                SUM(runner_count)::int AS runner_count
            FROM track_heatmap_cells
            WHERE {" AND ".join(cell_clauses)}
            GROUP BY zone, distance_band
        )
        , totals AS (
            SELECT
                grouped.*,
                SUM(win_count) OVER (PARTITION BY distance_band) AS band_wins,
                SUM(place_count) OVER (PARTITION BY distance_band) AS band_places
            FROM grouped
        )
        SELECT
            zone,
            distance_band,
            CASE distance_band
                WHEN 'sprint' THEN 'Sprint'
                WHEN 'mile' THEN 'Middle'
                WHEN 'staying' THEN 'Stayer'
                ELSE 'All distances'
            END AS distance_from_finish_band,
            ROUND(win_count::numeric * 100.0 / NULLIF(band_wins, 0), 2)::float AS win_rate,
            ROUND(place_count::numeric * 100.0 / NULLIF(band_places, 0), 2)::float AS place_rate,
            (win_count::numeric / NULLIF(band_wins, 0))::float AS intensity
        FROM totals
        WHERE runner_count > 0
        ORDER BY
            CASE distance_band WHEN 'sprint' THEN 0 WHEN 'mile' THEN 1 WHEN 'staying' THEN 2 ELSE 3 END,
            CASE zone WHEN 'inside' THEN 0 WHEN 'middle' THEN 1 WHEN 'outside' THEN 2 ELSE 3 END
        """,
        *params,
    )
    if not rows:
        rows = await fetch_all(
            request,
            f"""
            WITH aggregated AS (
                SELECT
                    {RELATIVE_BARRIER_ZONE_SQL.format(column='relative_barrier')} AS zone,
                    {DISTANCE_BAND_SQL.format(column='distance_m')} AS distance_from_finish_band,
                    COUNT(*)::int AS runner_count,
                    COUNT(*) FILTER (WHERE won)::int AS win_count,
                    COUNT(*) FILTER (WHERE placed)::int AS place_count
                FROM barrier_outcomes
                WHERE {" AND ".join(outcome_clauses)}
                GROUP BY 1, 2
            ),
            rates AS (
                SELECT
                    zone,
                    distance_from_finish_band,
                    runner_count,
                    ROUND(win_count::numeric * 100.0 / NULLIF(runner_count, 0), 2) AS win_rate,
                    ROUND(place_count::numeric * 100.0 / NULLIF(runner_count, 0), 2) AS place_rate
                FROM aggregated
                WHERE runner_count > 0
            )
            SELECT
                zone,
                distance_from_finish_band,
                win_rate::float AS win_rate,
                place_rate::float AS place_rate,
                CASE
                    WHEN COALESCE(MAX(win_rate) OVER (), 0) = 0
                         AND COALESCE(MAX(place_rate) OVER (), 0) = 0
                    THEN 0::float
                    ELSE ROUND(
                        LEAST(
                            1.0,
                            COALESCE(win_rate / NULLIF(MAX(win_rate) OVER (), 0), 0) * 0.65
                            + COALESCE(place_rate / NULLIF(MAX(place_rate) OVER (), 0), 0) * 0.35
                        ),
                        4
                    )::float
                END AS intensity
            FROM rates
            ORDER BY
                CASE zone
                    WHEN 'inside' THEN 1
                    WHEN 'middle' THEN 2
                    WHEN 'outside' THEN 3
                    ELSE 4
                END,
                CASE distance_from_finish_band
                    WHEN 'sprint' THEN 1
                    WHEN 'mile' THEN 2
                    WHEN 'staying' THEN 3
                    ELSE 4
                END
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


@router.get(
    "/{track_name}/weather",
    response_model=WeatherResponse,
    summary="Live weather and soil moisture",
)
async def get_weather(
    request: Request,
    track_name: str,
    since: str | None = None,
    resolution: str = "raw",
):
    query_track = canonical_track_name(track_name)
    station = await fetch_row(
        request,
        """
        SELECT id, label
        FROM weather_stations
        WHERE LOWER(track_name) = LOWER($1) AND active = true
        ORDER BY id
        LIMIT 1
        """,
        query_track,
    )
    if station is None:
        return WeatherResponse(
            track_name=track_name, station_label=None, current=None, soil_moisture=[], history=[]
        )

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
        soil_moisture=[
            SoilMoistureReading(**row) for row in soil if row["moisture_pct"] is not None
        ],
        history=history,
    )


@router.get(
    "/{track_name}/conditions", response_model=ConditionsResponse, summary="Track condition ratings"
)
async def get_conditions(request: Request, track_name: str):
    query_track = canonical_track_name(track_name)
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
        query_track,
    )
    current = ConditionReading(**rows[0]) if rows else None
    return ConditionsResponse(
        track_name=track_name,
        current_condition=current,
        recent_readings=[ConditionReading(**row) for row in rows],
    )
