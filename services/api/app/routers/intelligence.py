"""
Intelligence router — BETMAN proprietary scores, knowledge graph queries,
pre-race intelligence packages, and discovery pattern signals.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# ── Response models ───────────────────────────────────────────────────────────


class HorseScores(BaseModel):
    race_id: int
    race_entry_id: int
    runner_id: int
    runner_name: str
    barrier: Optional[int] = None
    bc_score: Optional[float] = None
    gas_score: Optional[float] = None
    mis_score: Optional[float] = None
    sis_score: Optional[float] = None
    hfs_score: Optional[float] = None
    was_score: Optional[float] = None
    bms_score: Optional[float] = None
    tbi_score: Optional[float] = None
    value_score: Optional[float] = None
    alpha_score: Optional[float] = None
    market_price: Optional[float] = None
    implied_probability: Optional[float] = None
    betman_probability: Optional[float] = None
    calculated_at: Optional[str] = None


class PreRaceIntelligence(BaseModel):
    race_id: int
    race_name: str
    scores: list[HorseScores]
    track_bias: Optional[dict] = None
    track_conditions: Optional[str] = None
    dominant_pattern: Optional[str] = None
    top_signal: Optional[str] = None


class SignalPerformanceItem(BaseModel):
    signal_type: str
    period_days: int
    bets: int
    winners: int
    roi: Optional[float] = None
    strike_rate: Optional[float] = None
    edge: Optional[float] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/races/{race_id}/scores", response_model=list[HorseScores])
async def get_race_scores(race_id: int):
    """
    Return BETMAN proprietary scores for every runner in the race.
    Sorted by alpha_score descending (highest confidence first).

    Scores are calculated by services/scoring/ and refreshed continuously
    until race start.
    """
    # TODO: query horse_scores JOIN race_entries JOIN runners WHERE race_id = ?
    return []


@router.get("/races/{race_id}/intelligence", response_model=PreRaceIntelligence)
async def get_pre_race_intelligence(race_id: int):
    """
    Full pre-race intelligence package for a race:
    - All runner scores
    - Current track bias (TBI)
    - Active discovery patterns applied to this race
    - Top signal summary

    Designed to be called once per race load in any BETMAN client.
    """
    # TODO: aggregate scores, TBI, pattern_signals, weather for this race
    raise HTTPException(status_code=404, detail="Race not found")


@router.get("/horses/{runner_id}/scores", response_model=list[HorseScores])
async def get_horse_score_history(
    runner_id: int,
    limit: int = Query(default=20, le=100),
):
    """
    Return the score history for a runner across their most recent races.
    Useful for tracking model accuracy and identifying horses where
    BETMAN consistently identifies value.
    """
    # TODO: query score_history JOIN horse_scores WHERE runner_id = ? ORDER BY snapshot_at DESC
    return []


@router.get("/scores/leaderboard", response_model=list[HorseScores])
async def get_score_leaderboard(
    race_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    min_alpha: float = Query(default=70.0, description="Minimum alpha score"),
    limit: int = Query(default=20, le=100),
):
    """
    Return the highest alpha-score runners for the given date.
    The BETMAN Daily Leaderboard — horses where multiple signals are aligned.
    """
    # TODO: query horse_scores JOIN races JOIN race_entries WHERE race date = ? AND alpha_score >= min_alpha
    return []


@router.get("/signals/performance", response_model=list[SignalPerformanceItem])
async def get_signal_performance(
    period_days: int = Query(default=30, description="Lookback period in days"),
):
    """
    Return ROI and strike rate for each BETMAN signal type over the period.
    The source of truth for which signals are producing edge.
    """
    # TODO: query signal_performance WHERE period_days = ?
    return []


@router.get("/graph/query")
async def query_knowledge_graph(
    q: str = Query(..., description="Natural language or structured graph query"),
    limit: int = Query(default=20, le=100),
):
    """
    Query the BETMAN knowledge graph (entity_relationships table).

    Example queries:
    - "horses trained by X at Trentham over 1400m after rain"
    - "sires with >15% wet-track win rate where progeny average barrier < 6"

    Phase 1: structured filter parsing over entity_relationships.
    Phase 2: LLM-assisted query translation with Neo4j/AGE backend.
    """
    # TODO: parse q, run PostgreSQL recursive CTE or graph query
    return {"results": [], "query": q, "note": "Knowledge graph query engine — Phase 2 implementation"}
