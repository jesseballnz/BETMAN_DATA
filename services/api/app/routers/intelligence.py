"""
Intelligence router — BETMAN proprietary scores, knowledge graph queries,
pre-race intelligence packages, and discovery pattern signals.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db import fetch_all, fetch_row

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class HorseScores(BaseModel):
    race_id: int
    race_entry_id: int
    runner_id: int
    runner_name: str
    barrier: int | None = None
    bc_score: float | None = None
    gas_score: float | None = None
    mis_score: float | None = None
    sis_score: float | None = None
    hfs_score: float | None = None
    was_score: float | None = None
    bms_score: float | None = None
    tbi_score: float | None = None
    value_score: float | None = None
    alpha_score: float | None = None
    market_price: float | None = None
    implied_probability: float | None = None
    betman_probability: float | None = None
    calculated_at: str | None = None


class PreRaceIntelligence(BaseModel):
    race_id: int
    race_name: str
    scores: list[HorseScores]
    track_bias: dict | None = None
    track_conditions: str | None = None
    dominant_pattern: str | None = None
    top_signal: str | None = None


class SignalPerformanceItem(BaseModel):
    signal_type: str
    period_days: int
    bets: int
    winners: int
    roi: float | None = None
    strike_rate: float | None = None
    edge: float | None = None


@router.get("/races/{race_id}/scores", response_model=list[HorseScores])
async def get_race_scores(request: Request, race_id: int):
    rows = await fetch_all(
        request,
        """
        SELECT hs.race_id, hs.race_entry_id, hs.runner_id, run.name AS runner_name,
               re.barrier_number AS barrier, hs.bc_score, hs.gas_score, hs.mis_score,
               hs.sis_score, hs.hfs_score, hs.was_score, hs.bms_score, hs.tbi_score,
               hs.value_score, hs.alpha_score, hs.market_price, hs.implied_probability,
               hs.betman_probability, hs.calculated_at::text AS calculated_at
        FROM horse_scores hs
        JOIN race_entries re ON re.id = hs.race_entry_id
        JOIN runners run ON run.id = hs.runner_id
        WHERE hs.race_id = $1
        ORDER BY hs.alpha_score DESC NULLS LAST, run.name
        """,
        race_id,
    )
    return [HorseScores(**row) for row in rows]


@router.get("/races/{race_id}/intelligence", response_model=PreRaceIntelligence)
async def get_pre_race_intelligence(request: Request, race_id: int):
    race = await fetch_row(
        request,
        """
        SELECT r.id, COALESCE(r.name, CONCAT('Race ', r.race_number)) AS race_name,
               m.track_name, COALESCE(r.surface, m.surface) AS surface,
               tc.condition_code, tc.condition_category
        FROM races r
        JOIN meetings m ON m.id = r.meeting_id
        LEFT JOIN LATERAL (
            SELECT condition_code, condition_category
            FROM track_condition_readings tcr
            WHERE tcr.race_id = r.id OR (tcr.race_id IS NULL AND tcr.meeting_id = m.id)
            ORDER BY CASE WHEN tcr.race_id = r.id THEN 0 ELSE 1 END, tcr.recorded_at DESC
            LIMIT 1
        ) tc ON TRUE
        WHERE r.id = $1
        """,
        race_id,
    )
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")

    scores = await get_race_scores(request, race_id)
    pattern = await fetch_row(
        request,
        """
        SELECT dp.description
        FROM pattern_signals ps
        JOIN discovered_patterns dp ON dp.id = ps.pattern_id
        WHERE ps.race_id = $1
        ORDER BY ps.signal_strength DESC, ps.generated_at DESC
        LIMIT 1
        """,
        race_id,
    )
    signal = await fetch_row(
        request,
        """
        SELECT movement_type, movement_pct, from_price, to_price
        FROM odds_movements
        WHERE race_id = $1
        ORDER BY ABS(movement_pct) DESC, detected_at DESC
        LIMIT 1
        """,
        race_id,
    )
    track_bias = await fetch_row(
        request,
        """
        SELECT AVG(win_rate)::float AS avg_win_rate, AVG(place_rate)::float AS avg_place_rate,
               MAX(intensity)::float AS max_intensity
        FROM track_heatmap_cells
        WHERE LOWER(track_name) = LOWER($1)
          AND surface = COALESCE($2, surface)
          AND ($3::text IS NULL OR condition_category = $3)
        """,
        race["track_name"],
        race["surface"],
        race["condition_category"],
    )

    return PreRaceIntelligence(
        race_id=race_id,
        race_name=race["race_name"],
        scores=scores,
        track_bias=track_bias,
        track_conditions=" ".join(
            filter(None, [race.get("condition_category"), race.get("condition_code")])
        )
        or None,
        dominant_pattern=pattern["description"] if pattern else None,
        top_signal=(
            (
                f"{signal['movement_type']} "
                f"{float(signal['movement_pct']):.1f}% "
                f"({float(signal['from_price']):.2f}→{float(signal['to_price']):.2f})"
            )
            if signal and signal["movement_pct"] is not None
            else None
        ),
    )


@router.get("/horses/{runner_id}/scores", response_model=list[HorseScores])
async def get_horse_score_history(
    request: Request,
    runner_id: int,
    limit: int = Query(default=20, le=100),
):
    rows = await fetch_all(
        request,
        """
        SELECT hs.race_id, hs.race_entry_id, hs.runner_id, run.name AS runner_name,
               re.barrier_number AS barrier, hs.bc_score, hs.gas_score, hs.mis_score,
               hs.sis_score, hs.hfs_score, hs.was_score, hs.bms_score, hs.tbi_score,
               hs.value_score, hs.alpha_score, hs.market_price, hs.implied_probability,
               hs.betman_probability, hs.calculated_at::text AS calculated_at
        FROM horse_scores hs
        JOIN race_entries re ON re.id = hs.race_entry_id
        JOIN runners run ON run.id = hs.runner_id
        WHERE hs.runner_id = $1
        ORDER BY hs.calculated_at DESC
        LIMIT $2
        """,
        runner_id,
        limit,
    )
    return [HorseScores(**row) for row in rows]


@router.get("/scores/leaderboard", response_model=list[HorseScores])
async def get_score_leaderboard(
    request: Request,
    race_date: date | None = Query(default=None, description="YYYY-MM-DD"),
    min_alpha: float = Query(default=70.0, description="Minimum alpha score"),
    limit: int = Query(default=20, le=100),
):
    rows = await fetch_all(
        request,
        """
        SELECT hs.race_id, hs.race_entry_id, hs.runner_id, run.name AS runner_name,
               re.barrier_number AS barrier, hs.bc_score, hs.gas_score, hs.mis_score,
               hs.sis_score, hs.hfs_score, hs.was_score, hs.bms_score, hs.tbi_score,
               hs.value_score, hs.alpha_score, hs.market_price, hs.implied_probability,
               hs.betman_probability, hs.calculated_at::text AS calculated_at
        FROM horse_scores hs
        JOIN race_entries re ON re.id = hs.race_entry_id
        JOIN races r ON r.id = hs.race_id
        JOIN meetings m ON m.id = r.meeting_id
        JOIN runners run ON run.id = hs.runner_id
        WHERE hs.alpha_score >= $1
          AND (
            $2::date IS NULL
            OR m.meeting_date = $2::date
            OR hs.calculated_at::date = $2::date
          )
        ORDER BY hs.alpha_score DESC, hs.calculated_at DESC
        LIMIT $3
        """,
        min_alpha,
        race_date,
        limit,
    )
    return [HorseScores(**row) for row in rows]


@router.get("/signals/performance", response_model=list[SignalPerformanceItem])
async def get_signal_performance(
    request: Request,
    period_days: int = Query(default=30, description="Lookback period in days"),
):
    rows = await fetch_all(
        request,
        """
        SELECT ms.signal_type, $1::int AS period_days,
               COUNT(*)::int AS bets,
               COUNT(*) FILTER (WHERE re.final_position = 1)::int AS winners,
               ROUND((AVG(CASE
                    WHEN lp.closing_price IS NULL THEN NULL
                    WHEN re.final_position = 1 THEN lp.closing_price - 1
                    ELSE -1
               END) * 100)::numeric, 2)::float AS roi,
               ROUND(
                  COUNT(*) FILTER (WHERE re.final_position = 1)::numeric
                  * 100.0 / NULLIF(COUNT(*), 0),
                  2
               )::float AS strike_rate,
               ROUND(((AVG(CASE WHEN re.final_position = 1 THEN 1.0 ELSE 0.0 END) - 0.1) * 100)::numeric, 2)::float AS edge
        FROM market_signals ms
        JOIN race_entries re ON re.id = ms.race_entry_id
        LEFT JOIN LATERAL (
            SELECT COALESCE(os.win_sp, os.win_price)::float AS closing_price
            FROM odds_snapshots os
            WHERE os.race_entry_id = re.id
              AND COALESCE(os.win_sp, os.win_price) IS NOT NULL
            ORDER BY os.captured_at DESC
            LIMIT 1
        ) lp ON TRUE
        WHERE ms.detected_at >= NOW() - make_interval(days => $1)
        GROUP BY ms.signal_type
        ORDER BY roi DESC NULLS LAST, strike_rate DESC
        """,
        period_days,
    )
    return [SignalPerformanceItem(**row) for row in rows]


@router.get("/graph/query")
async def query_knowledge_graph(
    q: str = Query(..., description="Natural language or structured graph query"),
    limit: int = Query(default=20, le=100),
):
    return {
        "results": [],
        "query": q,
        "limit": limit,
        "note": "Knowledge graph query engine — Phase 2 implementation",
    }
