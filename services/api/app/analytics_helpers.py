from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def compute_person_metrics(
    rows: list[dict[str, Any]],
    *,
    min_runners: int = 1,
    order_by: str = "win_rate",
    descending: bool = True,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str | None], dict[str, Any]] = defaultdict(
        lambda: {
            "person": None,
            "split_value": None,
            "runners": 0,
            "wins": 0,
            "places": 0,
            "roi_profit": 0.0,
            "priced_runners": 0,
        }
    )

    for row in rows:
        person = row.get("person") or "Unknown"
        split_value = row.get("split_value")
        key = (person, split_value)
        item = grouped[key]
        item["person"] = person
        item["split_value"] = split_value
        item["runners"] += 1

        final_position = row.get("final_position")
        if final_position == 1:
            item["wins"] += 1
        if isinstance(final_position, int) and final_position <= 3:
            item["places"] += 1

        closing_price = _as_float(row.get("closing_price"))
        if closing_price is not None:
            item["priced_runners"] += 1
            item["roi_profit"] += (closing_price - 1.0) if final_position == 1 else -1.0

    results: list[dict[str, Any]] = []
    for item in grouped.values():
        runners = item["runners"]
        if runners < min_runners:
            continue
        priced_runners = item["priced_runners"]
        item["win_rate"] = round(item["wins"] * 100.0 / runners, 2) if runners else 0.0
        item["place_rate"] = round(item["places"] * 100.0 / runners, 2) if runners else 0.0
        item["roi"] = (
            round(item["roi_profit"] * 100.0 / priced_runners, 2) if priced_runners else None
        )
        del item["roi_profit"]
        del item["priced_runners"]
        results.append(item)

    valid_sort_keys = {"win_rate", "place_rate", "roi", "runners", "wins", "places"}
    sort_key = order_by if order_by in valid_sort_keys else "win_rate"
    results.sort(
        key=lambda item: (
            item.get(sort_key) is None,
            item.get(sort_key, 0),
            item["runners"],
            item["wins"],
        ),
        reverse=descending,
    )
    return results
