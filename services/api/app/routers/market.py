"""
Market intelligence router — steamers, drifters, smart money indicators,
tote pools, and odds compression signals.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.db import fetch_all

router = APIRouter(prefix="/market", tags=["market"])


class MarketSignalItem(BaseModel):
    id: int
    race_id: int
    race_entry_id: int | None = None
    runner_name: str | None = None
    signal_type: str
    magnitude: float
    detected_at: str
    time_to_jump_s: int | None = None
    evidence: dict | None = None


class SmartMoneyItem(BaseModel):
    id: int
    race_id: int
    race_entry_id: int
    runner_name: str | None = None
    indicator_type: str
    confidence: float
    detected_at: str


class OddsTickItem(BaseModel):
    race_entry_id: int
    runner_name: str | None = None
    price: float
    source: str
    captured_at: str
    time_to_jump_s: int | None = None


class TotePoolItem(BaseModel):
    race_id: int
    pool_type: str
    pool_size: float | None = None
    captured_at: str


@router.get("/signals", response_model=list[MarketSignalItem])
async def get_market_signals(
    request: Request,
    signal_type: str | None = Query(
        default=None,
        description=(
            "steamer, drifter, late_money, price_compression, smart_money, field_compression"
        ),
    ),
    race_id: int | None = None,
    min_magnitude: float = Query(default=0.5),
    limit: int = Query(default=50, le=200),
):
    params: list[object] = [min_magnitude]
    clauses = ["magnitude >= $1"]
    if signal_type is not None:
        params.append(signal_type)
        clauses.append(f"signal_type = ${len(params)}")
    if race_id is not None:
        params.append(race_id)
        clauses.append(f"race_id = ${len(params)}")
    params.append(limit)
    rows = await fetch_all(
        request,
        f"""
        SELECT ms.id, ms.race_id, ms.race_entry_id, run.name AS runner_name, ms.signal_type,
               ms.magnitude, ms.detected_at::text AS detected_at,
               ms.time_to_jump_s, ms.evidence_json AS evidence
        FROM market_signals ms
        LEFT JOIN race_entries re ON re.id = ms.race_entry_id
        LEFT JOIN runners run ON run.id = re.runner_id
        WHERE {" AND ".join(clauses)}
        ORDER BY ms.detected_at DESC
        LIMIT ${len(params)}
        """,
        *params,
    )
    return [MarketSignalItem(**row) for row in rows]


@router.get("/steamers", response_model=list[MarketSignalItem])
async def get_steamers(
    request: Request,
    race_date: str | None = Query(default=None, description="YYYY-MM-DD, defaults to today"),
    limit: int = Query(default=20, le=100),
):
    rows = await fetch_all(
        request,
        """
        SELECT om.id, om.race_id, om.race_entry_id, run.name AS runner_name,
               om.movement_type AS signal_type, ABS(om.movement_pct)::float AS magnitude,
               om.detected_at::text AS detected_at, om.time_to_jump_s,
               jsonb_build_object(
                   'from_price', om.from_price,
                   'to_price', om.to_price,
                   'source', om.source
               ) AS evidence
        FROM odds_movements om
        JOIN races r ON r.id = om.race_id
        JOIN meetings m ON m.id = r.meeting_id
        JOIN race_entries re ON re.id = om.race_entry_id
        JOIN runners run ON run.id = re.runner_id
        WHERE om.movement_type = ANY(ARRAY['steam', 'firm', 'late_firm'])
          AND om.movement_pct < 0
          AND ($1::date IS NULL OR m.meeting_date = $1::date)
        ORDER BY ABS(om.movement_pct) DESC, om.detected_at DESC
        LIMIT $2
        """,
        race_date,
        limit,
    )
    return [MarketSignalItem(**row) for row in rows]


@router.get("/drifters", response_model=list[MarketSignalItem])
async def get_drifters(
    request: Request,
    race_date: str | None = Query(default=None, description="YYYY-MM-DD, defaults to today"),
    limit: int = Query(default=20, le=100),
):
    rows = await fetch_all(
        request,
        """
        SELECT om.id, om.race_id, om.race_entry_id, run.name AS runner_name,
               om.movement_type AS signal_type, ABS(om.movement_pct)::float AS magnitude,
               om.detected_at::text AS detected_at, om.time_to_jump_s,
               jsonb_build_object(
                   'from_price', om.from_price,
                   'to_price', om.to_price,
                   'source', om.source
               ) AS evidence
        FROM odds_movements om
        JOIN races r ON r.id = om.race_id
        JOIN meetings m ON m.id = r.meeting_id
        JOIN race_entries re ON re.id = om.race_entry_id
        JOIN runners run ON run.id = re.runner_id
        WHERE om.movement_type = ANY(ARRAY['drift', 'blowout'])
          AND om.movement_pct > 0
          AND ($1::date IS NULL OR m.meeting_date = $1::date)
        ORDER BY ABS(om.movement_pct) DESC, om.detected_at DESC
        LIMIT $2
        """,
        race_date,
        limit,
    )
    return [MarketSignalItem(**row) for row in rows]


@router.get("/smart-money", response_model=list[SmartMoneyItem])
async def get_smart_money(
    request: Request,
    race_date: str | None = Query(default=None, description="YYYY-MM-DD, defaults to today"),
    min_confidence: float = Query(default=0.7),
    limit: int = Query(default=20, le=100),
):
    rows = await fetch_all(
        request,
        """
        SELECT smi.id, smi.race_id, smi.race_entry_id, run.name AS runner_name,
               smi.indicator_type, smi.confidence::float AS confidence,
               smi.detected_at::text AS detected_at
        FROM smart_money_indicators smi
        JOIN races r ON r.id = smi.race_id
        JOIN meetings m ON m.id = r.meeting_id
        JOIN race_entries re ON re.id = smi.race_entry_id
        JOIN runners run ON run.id = re.runner_id
        WHERE smi.confidence >= $1
          AND ($2::date IS NULL OR m.meeting_date = $2::date)
        ORDER BY smi.confidence DESC, smi.detected_at DESC
        LIMIT $3
        """,
        min_confidence,
        race_date,
        limit,
    )
    return [SmartMoneyItem(**row) for row in rows]


@router.get("/races/{race_id}/odds-ticks", response_model=list[OddsTickItem])
async def get_race_odds_ticks(
    request: Request,
    race_id: int,
    source: str | None = None,
    runner_id: int | None = None,
):
    params: list[object] = [race_id]
    clauses = ["fot.race_id = $1"]
    if source is not None:
        params.append(source)
        clauses.append(f"fot.source = ${len(params)}")
    if runner_id is not None:
        params.append(runner_id)
        clauses.append(f"re.runner_id = ${len(params)}")
    rows = await fetch_all(
        request,
        f"""
        SELECT fot.race_entry_id, run.name AS runner_name, fot.price::float AS price,
               fot.source, fot.captured_at::text AS captured_at, fot.time_to_jump_s
        FROM fixed_odds_ticks fot
        JOIN race_entries re ON re.id = fot.race_entry_id
        JOIN runners run ON run.id = re.runner_id
        WHERE {" AND ".join(clauses)}
        ORDER BY fot.captured_at ASC
        """,
        *params,
    )
    return [OddsTickItem(**row) for row in rows]


@router.get("/races/{race_id}/tote-pools", response_model=list[TotePoolItem])
async def get_race_tote_pools(request: Request, race_id: int):
    rows = await fetch_all(
        request,
        """
        SELECT race_id, pool_type, pool_size::float AS pool_size, captured_at::text AS captured_at
        FROM tote_pools
        WHERE race_id = $1
        ORDER BY pool_type, captured_at
        """,
        race_id,
    )
    return [TotePoolItem(**row) for row in rows]
