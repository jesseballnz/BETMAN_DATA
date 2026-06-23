"""
Score Engine — coordinates score calculation for all upcoming races.

Each race is scored independently. The engine:
  1. Polls for upcoming races (next 4 hours)
  2. For each race, computes all 10 BETMAN scores per runner
  3. Writes results to horse_scores
  4. Publishes a Redis event for downstream consumers

Score computation order (dependencies):
  GAS → needs barrier_statistics
  TBI → needs track_bias_index
  WAS → needs weather_readings + pedigree_affinities
  BMS → needs pedigree_affinities + bloodline_performance
  MIS → needs fixed_odds_ticks + market_signals
  SIS → needs trainer_stats + stable_signals
  HFS → needs heatmap_scores + csi_readings + behaviour_observations
  BC  → needs all of the above (XGBoost model)
  VS  → needs BC + current market price
  α   → weighted combination of all
"""

import asyncio
from datetime import datetime, timezone

import structlog

from app.config import Settings

log = structlog.get_logger(__name__)


class ScoreEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._db = None
        self._redis = None

    async def run(self, shutdown: asyncio.Event):
        """Main loop — runs until shutdown event is set."""
        log.info("score_engine.starting")
        while not shutdown.is_set():
            try:
                await self._score_cycle()
            except Exception:
                log.exception("score_engine.cycle_error")
            await asyncio.wait_for(
                shutdown.wait(),
                timeout=self.settings.score_refresh_interval_s,
            )

    async def _score_cycle(self):
        """Fetch upcoming races and recompute all scores."""
        log.debug("score_engine.cycle_start", timestamp=datetime.now(timezone.utc).isoformat())
        # TODO:
        # 1. Query races WHERE scheduled_start_time BETWEEN now() AND now() + interval '4 hours'
        # 2. For each race, call _score_race(race_id)
        # 3. Write to horse_scores (upsert on race_id + race_entry_id)
        # 4. Publish betman:scores:{race_id} to Redis

    async def _score_race(self, race_id: int) -> list[dict]:
        """Compute scores for all runners in a race."""
        # TODO: implement per-runner score computation
        # Returns list of horse_score dicts ready for DB upsert
        return []

    async def _compute_gas(self, race_id: int, race_entry_id: int, barrier: int, context: dict) -> float | None:
        """
        Gate Advantage Score — see docs/betman-scores.md for formula.
        Returns 0–100 or None if insufficient data.
        """
        # TODO: query barrier_statistics for this track/surface/distance/condition/field_size
        return None

    async def _compute_mis(self, race_id: int, race_entry_id: int) -> float | None:
        """
        Market Intelligence Score — steam + late_firm + compression signals.
        """
        # TODO: query market_signals, fixed_odds_ticks in last 30 minutes
        return None

    async def _compute_sis(self, race_id: int, race_entry_id: int, trainer: str) -> float | None:
        """
        Stable Intent Score — trainer patterns + market alignment.
        """
        # TODO: query trainer_stats, stable_signals
        return None

    async def _compute_hfs(self, race_id: int, race_entry_id: int) -> float | None:
        """
        Heatmap Fitness Score — only if sensor data exists.
        """
        # TODO: query heatmap_scores, csi_readings, behaviour_observations
        return None

    async def _compute_was(self, runner_id: int, condition: dict) -> float | None:
        """
        Weather Affinity Score — pedigree + history vs current conditions.
        """
        # TODO: query pedigree_affinities, runner history at this condition_category
        return None

    async def _compute_bms(self, runner_id: int, context: dict) -> float | None:
        """
        Bloodline Match Score — sire affinities for this track/distance/condition.
        """
        # TODO: query pedigree_affinities for the runner's sire
        return None

    async def _compute_tbi(self, race_id: int, barrier: int, race_style: str) -> float | None:
        """
        Track Bias Index score — how much today's track bias favours this runner.
        """
        # TODO: query track_bias_index for today's meeting
        return None

    async def _compute_bc(self, features: dict) -> float | None:
        """
        BETMAN Confidence — XGBoost win probability estimate.
        """
        # TODO: load model, run inference on features dict
        return None

    async def _compute_value(self, bc: float | None, market_price: float | None) -> float | None:
        """
        Value Score — BC implied probability vs market implied probability.
        """
        if bc is None or market_price is None or market_price <= 0:
            return None
        betman_prob = bc / 100.0
        market_prob = 1.0 / market_price
        edge = betman_prob - market_prob
        return max(0.0, min(100.0, 50.0 + edge * 500.0))

    async def _compute_alpha(self, scores: dict) -> float | None:
        """
        Alpha Score — weighted combination of all component scores.
        See docs/betman-scores.md for weights.
        """
        weights = {
            "bc_score":    0.25,
            "mis_score":   0.20,
            "value_score": 0.20,
            "sis_score":   0.10,
            "gas_score":   0.10,
            "tbi_score":   0.05,
            "hfs_score":   0.05,
            "was_score":   0.03,
            "bms_score":   0.02,
        }
        total_weight = 0.0
        weighted_sum = 0.0
        for key, weight in weights.items():
            val = scores.get(key)
            if val is not None:
                weighted_sum += val * weight
                total_weight += weight
        if total_weight < 0.50:
            return None  # insufficient data
        return weighted_sum / total_weight
