"""
Discovery router — AI-discovered patterns, nightly run results, and generated signals.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db import fetch_all, fetch_row

router = APIRouter(prefix="/discovery", tags=["discovery"])


class DiscoveredPatternItem(BaseModel):
    id: int
    pattern_type: str
    description: str
    parameters: dict
    roi: float | None = None
    confidence: float
    sample_size: int | None = None
    first_detected: str
    valid_until: str | None = None
    active: bool


class PatternSignalItem(BaseModel):
    pattern_id: int
    pattern_description: str
    race_id: int
    race_entry_id: int | None = None
    runner_name: str | None = None
    signal_strength: float
    generated_at: str


class DiscoveryRunItem(BaseModel):
    id: int
    job_type: str
    started_at: str
    finished_at: str | None = None
    status: str
    patterns_found: int
    signals_emitted: int


@router.get("/patterns", response_model=list[DiscoveredPatternItem])
async def get_discovered_patterns(
    request: Request,
    pattern_type: str | None = Query(
        default=None,
        description="gate_bias, trainer_trend, sire_trend, market_anomaly, weather_correlation, heatmap_correlation, combination",
    ),
    min_roi: float | None = Query(default=None, description="Minimum estimated ROI"),
    min_confidence: float = Query(default=0.7),
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, le=200),
):
    params: list[object] = [min_confidence]
    clauses = ["confidence >= $1"]
    if pattern_type is not None:
        params.append(pattern_type)
        clauses.append(f"pattern_type = ${len(params)}")
    if min_roi is not None:
        params.append(min_roi)
        clauses.append(f"roi >= ${len(params)}")
    if active_only:
        clauses.append("active = true")
    params.append(limit)
    rows = await fetch_all(
        request,
        f"""
        SELECT id, pattern_type, description, parameters_json AS parameters, roi, confidence,
               sample_size, first_detected::text AS first_detected,
               valid_until::text AS valid_until, active
        FROM discovered_patterns
        WHERE {' AND '.join(clauses)}
        ORDER BY roi DESC NULLS LAST, confidence DESC, first_detected DESC
        LIMIT ${len(params)}
        """,
        *params,
    )
    return [DiscoveredPatternItem(**row) for row in rows]


@router.get("/signals", response_model=list[PatternSignalItem])
async def get_pattern_signals(
    request: Request,
    race_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    race_id: int | None = None,
    min_strength: float = Query(default=0.6),
    limit: int = Query(default=50, le=200),
):
    params: list[object] = [min_strength]
    clauses = ["ps.signal_strength >= $1"]
    if race_date is not None:
        params.append(race_date)
        clauses.append(f"m.meeting_date = ${len(params)}::date")
    if race_id is not None:
        params.append(race_id)
        clauses.append(f"ps.race_id = ${len(params)}")
    params.append(limit)
    rows = await fetch_all(
        request,
        f"""
        SELECT ps.pattern_id, dp.description AS pattern_description, ps.race_id,
               ps.race_entry_id, run.name AS runner_name,
               ps.signal_strength::float AS signal_strength,
               ps.generated_at::text AS generated_at
        FROM pattern_signals ps
        JOIN discovered_patterns dp ON dp.id = ps.pattern_id
        JOIN races r ON r.id = ps.race_id
        JOIN meetings m ON m.id = r.meeting_id
        LEFT JOIN race_entries re ON re.id = ps.race_entry_id
        LEFT JOIN runners run ON run.id = re.runner_id
        WHERE {' AND '.join(clauses)}
        ORDER BY ps.generated_at DESC, ps.signal_strength DESC
        LIMIT ${len(params)}
        """,
        *params,
    )
    return [PatternSignalItem(**row) for row in rows]


@router.get("/runs", response_model=list[DiscoveryRunItem])
async def get_discovery_runs(request: Request, limit: int = Query(default=10, le=100)):
    rows = await fetch_all(
        request,
        """
        SELECT id, job_type, started_at::text AS started_at, finished_at::text AS finished_at,
               status, patterns_found, signals_emitted
        FROM discovery_runs
        ORDER BY started_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [DiscoveryRunItem(**row) for row in rows]


@router.get("/patterns/by-gate")
async def get_gate_bias_patterns(
    request: Request,
    track_name: str | None = None,
    condition_category: str | None = None,
    limit: int = Query(default=20, le=100),
):
    params: list[object] = []
    clauses = ["pattern_type = 'gate_bias'", "active = true"]
    if track_name is not None:
        params.append(track_name)
        clauses.append(f"LOWER(COALESCE(parameters_json->>'track', parameters_json->>'track_name', '')) = LOWER(${len(params)})")
    if condition_category is not None:
        params.append(condition_category)
        clauses.append(f"LOWER(COALESCE(parameters_json->>'condition', parameters_json->>'condition_category', '')) = LOWER(${len(params)})")
    params.append(limit)
    rows = await fetch_all(
        request,
        f"""
        SELECT id, pattern_type, description, parameters_json AS parameters, roi, confidence,
               sample_size, first_detected::text AS first_detected,
               valid_until::text AS valid_until, active
        FROM discovered_patterns
        WHERE {' AND '.join(clauses)}
        ORDER BY roi DESC NULLS LAST, confidence DESC
        LIMIT ${len(params)}
        """,
        *params,
    )
    return {
        "patterns": [DiscoveredPatternItem(**row).model_dump() for row in rows],
        "filters": {"track_name": track_name, "condition_category": condition_category},
    }


@router.get("/patterns/{pattern_id}", response_model=DiscoveredPatternItem)
async def get_pattern_detail(request: Request, pattern_id: int):
    row = await fetch_row(
        request,
        """
        SELECT id, pattern_type, description, parameters_json AS parameters, roi, confidence,
               sample_size, first_detected::text AS first_detected,
               valid_until::text AS valid_until, active
        FROM discovered_patterns WHERE id = $1
        """,
        pattern_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return DiscoveredPatternItem(**row)
