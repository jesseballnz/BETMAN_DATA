"""
Pedigree router — bloodline performance, sire affinities, and breed-based recommendations.
"""

from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/pedigree", tags=["Pedigree"])


class PedigreeDetail(BaseModel):
    runner_id: int
    runner_name: str
    sire: Optional[str] = None
    dam: Optional[str] = None
    damsire: Optional[str] = None
    grandsire_pat: Optional[str] = None
    grandsire_mat: Optional[str] = None
    family_line: Optional[str] = None
    colour: Optional[str] = None


class SirePerformanceItem(BaseModel):
    sire: str
    track_name: Optional[str] = None
    surface: Optional[str] = None
    condition_category: Optional[str] = None
    distance_band: Optional[str] = None
    runners: int
    wins: int
    win_rate: Optional[float] = None
    place_rate: Optional[float] = None
    avg_win_price: Optional[float] = None
    roi: Optional[float] = None


class SireAffinityItem(BaseModel):
    sire: str
    affinity_type: str
    context_track: Optional[str] = None
    context_distance_band: Optional[str] = None
    context_condition: Optional[str] = None
    affinity_score: float
    win_rate: Optional[float] = None
    sample_size: Optional[int] = None


@router.get("/horses/{runner_id}", response_model=PedigreeDetail)
async def get_horse_pedigree(runner_id: int):
    """
    Return full pedigree for a runner. Includes sire, dam, damsire, and family line.
    """
    # TODO: SELECT from pedigrees WHERE runner_id = ?
    return PedigreeDetail(runner_id=runner_id, runner_name="Unknown")


@router.get("/sires/{sire_name}/performance", response_model=list[SirePerformanceItem])
async def get_sire_performance(
    sire_name: str,
    track_name: Optional[str] = None,
    condition_category: Optional[str] = None,
    distance_band: Optional[str] = None,
):
    """
    Return performance statistics for all progeny of the named sire,
    optionally filtered by track, conditions, and distance band.

    Key for identifying bloodline affinities — "which sires excel at Ruakaka on Heavy 10?"
    """
    # TODO: SELECT from bloodline_performance WHERE sire ILIKE ? AND (filters)
    return []


@router.get("/sires/{sire_name}/affinities", response_model=list[SireAffinityItem])
async def get_sire_affinities(sire_name: str):
    """
    Return all calculated affinities for a sire line across different race contexts.
    Affinity > 1.0 = better than expected, < 1.0 = below expected.
    """
    # TODO: SELECT from pedigree_affinities WHERE sire ILIKE ?
    return []


@router.get("/sires/top-wet-track", response_model=list[SirePerformanceItem])
async def get_top_wet_track_sires(
    condition_category: str = Query(default="heavy", description="heavy or soft"),
    min_runners: int = Query(default=20),
    limit: int = Query(default=20, le=100),
):
    """
    Return sires sorted by wet-track ROI. The starting point for rain-day research.
    """
    # TODO: SELECT from bloodline_performance WHERE condition_category = ? AND runners >= ? ORDER BY roi DESC
    return []
