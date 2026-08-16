"""Deterministic backend scoring and prediction persistence.

The first production-safe model is deliberately transparent: market prior plus
historical evidence, normalized across the field. It contains no random
simulation and records the exact feature package used for every prediction.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from app.analysis_features import (
    FEATURE_VERSION,
    build_runner_features,
    capped_kelly,
    deterministic_probabilities,
    evidence_probability,
    market_probabilities,
)
from app.config import Settings

log = structlog.get_logger(__name__)
MODEL_VERSION = "deterministic-market-evidence-v1"


class ScoreEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pool: asyncpg.Pool | None = None

    async def run(self, shutdown: asyncio.Event):
        log.info("score_engine.starting")
        if not self.settings.database_url:
            raise RuntimeError("DATABASE_URL is required for scoring")
        self._pool = await asyncpg.create_pool(self.settings.database_url, min_size=1, max_size=4)
        try:
            while not shutdown.is_set():
                try:
                    await self._score_cycle()
                except Exception as exc:
                    log.exception("score_engine.cycle_error", error=str(exc))
                try:
                    await asyncio.wait_for(
                        shutdown.wait(), timeout=self.settings.score_refresh_interval_s
                    )
                except asyncio.TimeoutError:
                    pass
        finally:
            await self._pool.close()
            self._pool = None

    async def _score_cycle(self):
        if self._pool is None:
            raise RuntimeError("score engine pool is not initialized")
        race_ids = await self._pool.fetch(
            """
            SELECT id FROM races
            WHERE status IN ('scheduled', 'running')
              AND scheduled_start_time BETWEEN now() - interval '30 minutes'
                                            AND now() + interval '48 hours'
            ORDER BY scheduled_start_time, id
            LIMIT 200
            """
        )
        for row in race_ids:
            await self._score_race(row["id"])

    async def _score_race(self, race_id: int) -> list[dict[str, Any]]:
        if self._pool is None:
            raise RuntimeError("score engine pool is not initialized")
        rows = await self._pool.fetch(
            """
            SELECT r.id AS race_id, r.distance_m, COALESCE(r.surface, m.surface) AS surface,
                   r.race_class_group, r.scheduled_start_time, m.track_name,
                   re.id AS race_entry_id, re.runner_id, re.barrier_number,
                   re.trainer, re.jockey_or_driver, re.weight_kg, ru.name AS runner_name,
                   COUNT(*) OVER ()::int AS field_size,
                   odds.price,
                   condition.condition_category,
                   barrier.barrier_win_rate,
                   trainer.trainer_win_rate
            FROM races r
            JOIN meetings m ON m.id = r.meeting_id
            JOIN race_entries re ON re.race_id = r.id AND NOT re.scratched
            JOIN runners ru ON ru.id = re.runner_id
            LEFT JOIN LATERAL (
                SELECT price::float AS price
                FROM fixed_odds_ticks
                WHERE race_entry_id = re.id
                  AND captured_at <= COALESCE(r.scheduled_start_time, now())
                ORDER BY captured_at DESC LIMIT 1
            ) odds ON true
            LEFT JOIN LATERAL (
                SELECT condition_category
                FROM track_condition_readings
                WHERE race_id = r.id OR (race_id IS NULL AND meeting_id = r.meeting_id)
                ORDER BY (race_id = r.id) DESC, recorded_at DESC LIMIT 1
            ) condition ON true
            LEFT JOIN LATERAL (
                SELECT AVG(won::int)::float AS barrier_win_rate
                FROM barrier_outcomes bo
                WHERE bo.track_name = m.track_name
                  AND bo.surface = COALESCE(r.surface, m.surface)
                  AND bo.barrier_number = re.barrier_number
                  AND bo.race_id <> r.id
            ) barrier ON true
            LEFT JOIN LATERAL (
                SELECT (win_rate / 100.0)::float AS trainer_win_rate
                FROM trainer_stats ts
                WHERE lower(ts.trainer) = lower(re.trainer)
                ORDER BY ts.runners DESC NULLS LAST LIMIT 1
            ) trainer ON true
            WHERE r.id = $1
            ORDER BY re.id
            """,
            race_id,
        )
        if not rows:
            return []

        prices = [float(row["price"]) if row["price"] is not None else None for row in rows]
        market = market_probabilities(prices)
        feature_rows: list[dict[str, Any]] = []
        evidence: list[float | None] = []
        for row, market_probability in zip(rows, market):
            raw = dict(row)
            features, missing = build_runner_features(raw, market_probability)
            evidence.append(evidence_probability(features))
            feature_rows.append(
                {
                    "row": raw,
                    "features": features,
                    "missing": missing,
                    "market_probability": market_probability,
                }
            )
        probabilities = deterministic_probabilities(market, evidence)
        calculated_at = datetime.now(timezone.utc)
        output: list[dict[str, Any]] = []

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for item, probability in zip(feature_rows, probabilities):
                    row = item["row"]
                    price = float(row["price"]) if row["price"] is not None else None
                    market_probability = item["market_probability"]
                    fair_odds = round(1.0 / probability, 4) if probability > 0 else None
                    edge = probability - market_probability if market_probability is not None else None
                    confidence = max(0.0, min(1.0, 0.5 + abs(edge or 0.0)))
                    stake = capped_kelly(probability, price)
                    provenance = {
                        "model_version": MODEL_VERSION,
                        "market_source": "fixed_odds_ticks" if price is not None else None,
                        "feature_source": FEATURE_VERSION,
                    }
                    await conn.execute(
                        """
                        INSERT INTO race_analysis_features (
                            race_id, race_entry_id, runner_id, generated_at,
                            source_cutoff_at, feature_version, feature_vector,
                            provenance, missing_features, market_price,
                            market_probability, model_probability, fair_odds, edge, confidence
                        ) VALUES ($1,$2,$3,$4,$4,$5,$6::jsonb,$7::jsonb,$8::jsonb,$9,$10,$11,$12,$13,$14)
                        ON CONFLICT (race_id, race_entry_id, feature_version) DO UPDATE SET
                            generated_at=EXCLUDED.generated_at,
                            source_cutoff_at=EXCLUDED.source_cutoff_at,
                            feature_vector=EXCLUDED.feature_vector,
                            provenance=EXCLUDED.provenance,
                            missing_features=EXCLUDED.missing_features,
                            market_price=EXCLUDED.market_price,
                            market_probability=EXCLUDED.market_probability,
                            model_probability=EXCLUDED.model_probability,
                            fair_odds=EXCLUDED.fair_odds,
                            edge=EXCLUDED.edge,
                            confidence=EXCLUDED.confidence
                        """,
                        race_id, row["race_entry_id"], row["runner_id"], calculated_at,
                        FEATURE_VERSION,
                        _json(item["features"]), _json(provenance), _json(item["missing"]),
                        price, market_probability, probability, fair_odds, edge, confidence,
                    )
                    await conn.execute(
                        """
                        INSERT INTO race_prediction_snapshots (
                            race_id, race_entry_id, generated_at, model_version,
                            probability, fair_odds, market_price, edge, stake_fraction
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        """,
                        race_id, row["race_entry_id"], calculated_at, MODEL_VERSION,
                        probability, fair_odds, price, edge, stake,
                    )
                    await conn.execute(
                        """
                        INSERT INTO horse_scores (
                            race_id, race_entry_id, runner_id, bc_score, value_score,
                            alpha_score, market_price, implied_probability,
                            betman_probability, calculated_at, model_version
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                        ON CONFLICT (race_id, race_entry_id) DO UPDATE SET
                            bc_score=EXCLUDED.bc_score, value_score=EXCLUDED.value_score,
                            alpha_score=EXCLUDED.alpha_score, market_price=EXCLUDED.market_price,
                            implied_probability=EXCLUDED.implied_probability,
                            betman_probability=EXCLUDED.betman_probability,
                            calculated_at=EXCLUDED.calculated_at, model_version=EXCLUDED.model_version
                        """,
                        race_id, row["race_entry_id"], row["runner_id"], probability * 100,
                        max(0.0, min(100.0, 50.0 + (edge or 0.0) * 500.0)),
                        probability * 100, price, market_probability, probability,
                        calculated_at, MODEL_VERSION,
                    )
                    output.append({"race_entry_id": row["race_entry_id"], "probability": probability})
        return output


def _json(value: Any) -> str:
    import json

    return json.dumps(value, separators=(",", ":"), default=str)
