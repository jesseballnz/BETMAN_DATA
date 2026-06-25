"""
Pedigree router — bloodline performance, sire affinities, and breed-based recommendations.

Canonical identity for a horse is horse_uuid (UUID). The legacy runner_id (integer)
is supported for convenience via the /horses/{runner_id} route which joins through
the runners table. The canonical lookup is /horses/by-uuid/{horse_uuid}.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db import fetch_all, fetch_row

router = APIRouter(prefix="/pedigree", tags=["pedigree"])


class PedigreeDetail(BaseModel):
    runner_id: int
    horse_uuid: UUID | None = None
    runner_name: str
    provider_name: str | None = None
    sire: str | None = None
    dam: str | None = None
    damsire: str | None = None
    grandsire_pat: str | None = None
    grandsire_mat: str | None = None
    family_line: str | None = None
    colour: str | None = None


class SirePerformanceItem(BaseModel):
    sire: str
    track_name: str | None = None
    surface: str | None = None
    condition_category: str | None = None
    distance_band: str | None = None
    runners: int
    wins: int
    win_rate: float | None = None
    place_rate: float | None = None
    avg_win_price: float | None = None
    roi: float | None = None


class SireAffinityItem(BaseModel):
    sire: str
    affinity_type: str
    context_track: str | None = None
    context_distance_band: str | None = None
    context_condition: str | None = None
    affinity_score: float
    win_rate: float | None = None
    sample_size: int | None = None


_PEDIGREE_SELECT = """
    SELECT
        p.runner_id,
        p.horse_uuid,
        r.name        AS runner_name,
        p.provider_name,
        p.sire,
        p.dam,
        p.damsire,
        p.grandsire_pat,
        p.grandsire_mat,
        p.family_line,
        p.colour
    FROM pedigrees p
    JOIN runners r ON r.id = p.runner_id
"""


@router.get("/horses/by-uuid/{horse_uuid}", response_model=PedigreeDetail)
async def get_horse_pedigree_by_uuid(request: Request, horse_uuid: UUID):
    """
    Return full pedigree for a horse identified by its canonical horse_uuid.
    Returns 404 when no pedigree record exists for the given UUID.
    """
    row = await fetch_row(
        request,
        f"{_PEDIGREE_SELECT} WHERE p.horse_uuid = $1",
        horse_uuid,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No pedigree found for horse_uuid {horse_uuid}",
        )
    return PedigreeDetail(**row)


@router.get("/horses/{runner_id}", response_model=PedigreeDetail)
async def get_horse_pedigree(request: Request, runner_id: int):
    """
    Return full pedigree for a runner by its integer runner_id.
    Prefer /horses/by-uuid/{horse_uuid} for canonical lookups.
    Returns 404 when no pedigree record exists for the runner.
    """
    row = await fetch_row(
        request,
        f"{_PEDIGREE_SELECT} WHERE p.runner_id = $1",
        runner_id,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No pedigree found for runner_id {runner_id}",
        )
    return PedigreeDetail(**row)


@router.get("/sires/top-wet-track", response_model=list[SirePerformanceItem])
async def get_top_wet_track_sires(
    request: Request,
    condition_category: str = Query(default="heavy", description="heavy or soft"),
    min_runners: int = Query(default=20),
    limit: int = Query(default=20, le=100),
):
    """
    Return sires sorted by wet-track ROI. The starting point for rain-day research.
    Returns an empty list when no bloodline performance data is available.
    """
    rows = await fetch_all(
        request,
        """
        SELECT sire, track_name, surface, condition_category, distance_band,
               runners, wins, win_rate::float AS win_rate,
               place_rate::float AS place_rate,
               avg_win_price::float AS avg_win_price,
               roi::float AS roi
        FROM bloodline_performance
        WHERE LOWER(condition_category) = LOWER($1)
          AND runners >= $2
        ORDER BY roi DESC NULLS LAST, wins DESC
        LIMIT $3
        """,
        condition_category,
        min_runners,
        limit,
    )
    return [SirePerformanceItem(**row) for row in rows]


@router.get("/sires/{sire_name}/performance", response_model=list[SirePerformanceItem])
async def get_sire_performance(
    request: Request,
    sire_name: str,
    track_name: str | None = None,
    condition_category: str | None = None,
    distance_band: str | None = None,
):
    """
    Return performance statistics for all progeny of the named sire,
    optionally filtered by track, conditions, and distance band.

    Key for identifying bloodline affinities — "which sires excel at Ruakaka on Heavy 10?"
    Returns an empty list when no data is available.
    """
    params: list[object] = [sire_name]
    clauses = ["LOWER(sire) = LOWER($1)"]
    if track_name is not None:
        params.append(track_name)
        clauses.append(f"LOWER(COALESCE(track_name, '')) = LOWER(${len(params)})")
    if condition_category is not None:
        params.append(condition_category)
        clauses.append(f"LOWER(COALESCE(condition_category, '')) = LOWER(${len(params)})")
    if distance_band is not None:
        params.append(distance_band)
        clauses.append(f"LOWER(COALESCE(distance_band, '')) = LOWER(${len(params)})")
    rows = await fetch_all(
        request,
        f"""
        SELECT sire, track_name, surface, condition_category, distance_band,
               runners, wins, win_rate::float AS win_rate,
               place_rate::float AS place_rate,
               avg_win_price::float AS avg_win_price,
               roi::float AS roi
        FROM bloodline_performance
        WHERE {" AND ".join(clauses)}
        ORDER BY wins DESC, roi DESC NULLS LAST
        """,
        *params,
    )
    return [SirePerformanceItem(**row) for row in rows]


@router.get("/sires/{sire_name}/affinities", response_model=list[SireAffinityItem])
async def get_sire_affinities(request: Request, sire_name: str):
    """
    Return all calculated affinities for a sire line across different race contexts.
    Affinity > 1.0 = better than expected, < 1.0 = below expected.
    Returns an empty list when no affinity data is available.
    """
    rows = await fetch_all(
        request,
        """
        SELECT sire, affinity_type, context_track, context_distance_band, context_condition,
               affinity_score::float AS affinity_score,
               win_rate::float AS win_rate,
               sample_size
        FROM pedigree_affinities
        WHERE LOWER(sire) = LOWER($1)
        ORDER BY affinity_score DESC
        """,
        sire_name,
    )
    return [SireAffinityItem(**row) for row in rows]
