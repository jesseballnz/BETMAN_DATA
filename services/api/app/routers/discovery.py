"""
Discovery router — AI-discovered patterns, nightly run results, and generated signals.
"""

from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/discovery", tags=["discovery"])


class DiscoveredPatternItem(BaseModel):
    id: int
    pattern_type: str
    description: str
    parameters: dict
    roi: Optional[float] = None
    confidence: float
    sample_size: Optional[int] = None
    first_detected: str
    valid_until: Optional[str] = None
    active: bool


class PatternSignalItem(BaseModel):
    pattern_id: int
    pattern_description: str
    race_id: int
    race_entry_id: Optional[int] = None
    runner_name: Optional[str] = None
    signal_strength: float
    generated_at: str


class DiscoveryRunItem(BaseModel):
    id: int
    job_type: str
    started_at: str
    finished_at: Optional[str] = None
    status: str
    patterns_found: int
    signals_emitted: int


@router.get("/patterns", response_model=list[DiscoveredPatternItem])
async def get_discovered_patterns(
    pattern_type: Optional[str] = Query(
        default=None,
        description="gate_bias, trainer_trend, sire_trend, market_anomaly, weather_correlation, heatmap_correlation, combination",
    ),
    min_roi: Optional[float] = Query(default=None, description="Minimum estimated ROI"),
    min_confidence: float = Query(default=0.7),
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, le=200),
):
    """
    Return all discovered patterns that meet the criteria.

    Example patterns:
    - "Barrier 2 at Awapuni is +18% ROI over last 90 days"
    - "Progeny of Savabeel outperform market expectation by 14% on Soft tracks"
    - "Horses with elevated breathing rate pre-race are underperforming by 22%"

    These are generated nightly by services/discovery/ and stored in discovered_patterns.
    """
    # TODO: SELECT from discovered_patterns WHERE active = ? AND ... ORDER BY roi DESC NULLS LAST
    return []


@router.get("/patterns/{pattern_id}", response_model=DiscoveredPatternItem)
async def get_pattern_detail(pattern_id: int):
    """Return full detail for a specific discovered pattern."""
    # TODO: SELECT from discovered_patterns WHERE id = ?
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Pattern not found")


@router.get("/signals", response_model=list[PatternSignalItem])
async def get_pattern_signals(
    race_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    race_id: Optional[int] = None,
    min_strength: float = Query(default=0.6),
    limit: int = Query(default=50, le=200),
):
    """
    Return generated signals from discovered patterns applied to specific races/runners.

    These represent the actionable output of the AI Discovery Engine —
    known profitable patterns that currently apply to today's races.
    """
    # TODO: SELECT from pattern_signals JOIN discovered_patterns WHERE ...
    return []


@router.get("/runs", response_model=list[DiscoveryRunItem])
async def get_discovery_runs(
    limit: int = Query(default=10, le=100),
):
    """
    Return the history of nightly AI discovery runs. Shows which jobs ran,
    how many patterns were found, and whether any failed.
    """
    # TODO: SELECT from discovery_runs ORDER BY started_at DESC LIMIT ?
    return []


@router.get("/patterns/by-gate")
async def get_gate_bias_patterns(
    track_name: Optional[str] = None,
    condition_category: Optional[str] = None,
    limit: int = Query(default=20, le=100),
):
    """
    Return gate bias patterns — the Gate Advantage Score (GAS) source data.

    Filters to pattern_type = 'gate_bias'.
    Useful for building track-specific barrier profiles.
    """
    # TODO: query discovered_patterns WHERE pattern_type = 'gate_bias' AND parameters @> ?
    return {"patterns": [], "filters": {"track_name": track_name, "condition_category": condition_category}}
