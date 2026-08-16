"""Pure, deterministic race-analysis feature construction.

This module deliberately contains no database or LLM logic. The database layer
supplies observations; these functions normalize them into a versioned package
that can be reproduced for audit and calibration.
"""

from __future__ import annotations

import math
from typing import Any

FEATURE_VERSION = "race-features-v1"


def distance_band(distance_m: int | None) -> str:
    if distance_m is None:
        return "unknown"
    if distance_m <= 1200:
        return "sprint"
    if distance_m <= 1600:
        return "mile"
    return "staying"


def market_probabilities(prices: list[float | None]) -> list[float | None]:
    """Return overround-adjusted implied probabilities in input order."""
    inverse = [1.0 / p if p and p > 1.0 else None for p in prices]
    total = sum(p for p in inverse if p is not None)
    if total <= 0:
        return [None] * len(prices)
    return [round(p / total, 8) if p is not None else None for p in inverse]


def _bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _logit(probability: float) -> float:
    p = _bounded(probability, 1e-6, 1 - 1e-6)
    return math.log(p / (1 - p))


def deterministic_probabilities(
    market: list[float | None],
    evidence: list[float | None],
    *,
    market_weight: float = 0.70,
) -> list[float]:
    """Blend market prior and evidence, then renormalize across the field.

    This is a transparent baseline model, not a claim of trained-model
    performance. It is intentionally deterministic and replaces browser-side
    pseudo-simulation until a validated trained model is installed.
    """
    raw: list[float] = []
    for market_p, evidence_p in zip(market, evidence):
        prior = market_p if market_p is not None else 1.0
        signal = evidence_p if evidence_p is not None else prior
        raw.append(math.exp(market_weight * _logit(prior) + (1 - market_weight) * _logit(signal)))
    total = sum(raw) or 1.0
    return [round(value / total, 8) for value in raw]


def capped_kelly(probability: float, price: float | None, *, cap: float = 0.05) -> float:
    """Quarter-Kelly-style capped stake fraction with hard input guards."""
    if price is None or price <= 1 or probability <= 0 or probability >= 1:
        return 0.0
    b = price - 1.0
    full_kelly = (probability * price - 1.0) / b
    return round(_bounded(full_kelly * 0.25, 0.0, cap), 6)


def build_runner_features(row: dict[str, Any], market_probability: float | None) -> tuple[dict[str, Any], list[str]]:
    """Build a JSON-safe feature vector and explicit missingness list."""
    fields = {
        "distance_m": row.get("distance_m"),
        "distance_band": distance_band(row.get("distance_m")),
        "surface": row.get("surface") or "unknown",
        "barrier_number": row.get("barrier_number"),
        "field_size": row.get("field_size"),
        "weight_kg": float(row["weight_kg"]) if row.get("weight_kg") is not None else None,
        "market_probability": market_probability,
        "barrier_win_rate": row.get("barrier_win_rate"),
        "trainer_win_rate": row.get("trainer_win_rate"),
        "jockey_win_rate": row.get("jockey_win_rate"),
        "condition_category": row.get("condition_category") or "unknown",
    }
    missing = [key for key, value in fields.items() if value is None]
    return fields, missing


def evidence_probability(features: dict[str, Any]) -> float | None:
    """Create a transparent evidence prior from available historical rates."""
    rates = [
        float(features[key])
        for key in ("barrier_win_rate", "trainer_win_rate", "jockey_win_rate")
        if features.get(key) is not None and 0 <= float(features[key]) <= 1
    ]
    if not rates:
        return None
    return _bounded(sum(rates) / len(rates), 0.01, 0.80)

