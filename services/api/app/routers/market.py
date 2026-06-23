"""
Market intelligence router — steamers, drifters, smart money indicators,
tote pools, and odds compression signals.
"""

from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/market", tags=["market"])


class MarketSignalItem(BaseModel):
    id: int
    race_id: int
    race_entry_id: Optional[int] = None
    runner_name: Optional[str] = None
    signal_type: str
    magnitude: float
    detected_at: str
    time_to_jump_s: Optional[int] = None
    evidence: Optional[dict] = None


class SmartMoneyItem(BaseModel):
    id: int
    race_id: int
    race_entry_id: int
    runner_name: Optional[str] = None
    indicator_type: str
    confidence: float
    detected_at: str


class OddsTickItem(BaseModel):
    race_entry_id: int
    runner_name: Optional[str] = None
    price: float
    source: str
    captured_at: str
    time_to_jump_s: Optional[int] = None


class TotePoolItem(BaseModel):
    race_id: int
    pool_type: str
    pool_size: Optional[float] = None
    captured_at: str


@router.get("/signals", response_model=list[MarketSignalItem])
async def get_market_signals(
    signal_type: Optional[str] = Query(
        default=None,
        description="steamer, drifter, late_money, price_compression, smart_money, field_compression",
    ),
    race_id: Optional[int] = None,
    min_magnitude: float = Query(default=0.5),
    limit: int = Query(default=50, le=200),
):
    """
    Return recent market signals. Filter by type and magnitude.

    Steamers and late money signals are the highest value — they indicate
    where informed money is flowing.
    """
    # TODO: SELECT from market_signals WHERE ... ORDER BY detected_at DESC LIMIT ?
    return []


@router.get("/steamers", response_model=list[MarketSignalItem])
async def get_steamers(
    race_date: Optional[str] = Query(default=None, description="YYYY-MM-DD, defaults to today"),
    limit: int = Query(default=20, le=100),
):
    """
    Return runners showing steaming patterns today.
    A steamer = >20% price firming in <5 minutes.
    """
    # TODO: SELECT from market_signals WHERE signal_type = 'steamer' AND race_date = ? ORDER BY magnitude DESC
    return []


@router.get("/drifters", response_model=list[MarketSignalItem])
async def get_drifters(
    race_date: Optional[str] = Query(default=None, description="YYYY-MM-DD, defaults to today"),
    limit: int = Query(default=20, le=100),
):
    """
    Return runners showing drifting patterns today.
    A drifter = >20% price blowout in <5 minutes.
    """
    # TODO: SELECT from market_signals WHERE signal_type = 'drifter' AND race_date = ?
    return []


@router.get("/smart-money", response_model=list[SmartMoneyItem])
async def get_smart_money(
    race_date: Optional[str] = Query(default=None, description="YYYY-MM-DD, defaults to today"),
    min_confidence: float = Query(default=0.7),
    limit: int = Query(default=20, le=100),
):
    """
    Return smart money indicators — high-confidence signals of coordinated informed betting.

    These are synthesised from multiple corroborating market signals:
    - Tote/fixed alignment
    - Coordinated firming across multiple bookmakers
    - Late money below threshold price
    """
    # TODO: SELECT from smart_money_indicators WHERE ... AND confidence >= ? ORDER BY detected_at DESC
    return []


@router.get("/races/{race_id}/odds-ticks", response_model=list[OddsTickItem])
async def get_race_odds_ticks(
    race_id: int,
    source: Optional[str] = None,
    runner_id: Optional[int] = None,
):
    """
    Return every recorded odds tick for a race — the complete price history.

    Use this to visualise the price journey for each runner from
    market open to jump. The raw material for computing MIS.
    """
    # TODO: SELECT from fixed_odds_ticks WHERE race_id = ? AND ... ORDER BY captured_at ASC
    return []


@router.get("/races/{race_id}/tote-pools", response_model=list[TotePoolItem])
async def get_race_tote_pools(race_id: int):
    """
    Return tote pool snapshots for a race, showing pool growth over time.
    """
    # TODO: SELECT from tote_pools WHERE race_id = ? ORDER BY pool_type, captured_at
    return []
