from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/tracks", tags=["tracks", "barrier-analysis", "weather"])


class BarrierStat(BaseModel):
    barrier_number: int
    relative_barrier: str
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
    distance_from_finish_band: str
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


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/{track_name}/barriers", response_model=BarrierAnalysisResponse,
            summary="Barrier win/place statistics")
async def get_barrier_analysis(
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
    """
    Barrier analysis for a track filtered by condition, surface, distance,
    and race class. Aggregated from barrier_outcomes and barrier_statistics.

    Example: most winning barriers on a Heavy 10 at Ellerslie over 1400–1600m.
    """
    # TODO: query barrier_statistics with filters, ORDER BY win_rate DESC
    return BarrierAnalysisResponse(
        track_name=track_name,
        surface=surface,
        filters={
            "condition_code": condition,
            "condition_category": condition_category,
            "distance_min": distance_min,
            "distance_max": distance_max,
            "race_class_group": race_class_group,
            "since": since,
        },
        sample_size=0,
        barriers=[],
    )


@router.get("/{track_name}/heatmap", response_model=HeatmapResponse,
            summary="Spatial barrier heat map")
async def get_heatmap(
    track_name: str,
    condition_category: str | None = None,
    surface: str = "turf",
    distance_band: str | None = None,
):
    """
    Spatial heat map data — intensity values per track zone and condition,
    ready to render over an SVG/canvas track diagram. Sourced from
    track_heatmap_cells, rebuilt after each race result.
    """
    return HeatmapResponse(
        track_name=track_name,
        surface=surface,
        condition_category=condition_category or "all",
        distance_band=distance_band,
        cells=[],
    )


@router.get("/{track_name}/weather", response_model=WeatherResponse,
            summary="Live weather and soil moisture")
async def get_weather(
    track_name: str,
    since: str | None = None,
    resolution: str = "raw",
):
    """
    Live and historical weather data from the WeatherLink station at this track,
    including per-probe soil moisture readings. The soil moisture array gives
    a spatial picture of track moisture that feeds into barrier analysis.
    """
    # TODO: check Redis state for current snapshot first (fast path),
    # fall back to DB query for historical data
    return WeatherResponse(
        track_name=track_name,
        station_label=None,
        current=None,
        soil_moisture=[],
        history=[],
    )


@router.get("/{track_name}/conditions", response_model=ConditionsResponse,
            summary="Track condition ratings")
async def get_conditions(track_name: str):
    """
    Current and recent official track condition ratings (H10, S6, G4, etc.)
    with penetrometer values and source attribution.
    """
    return ConditionsResponse(
        track_name=track_name,
        current_condition=None,
        recent_readings=[],
    )
