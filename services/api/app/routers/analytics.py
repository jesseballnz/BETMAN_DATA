from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.analytics_helpers import compute_person_metrics
from app.db import fetch_all

router = APIRouter(prefix="/analytics", tags=["analytics"])
VALID_GROUP_BYS = {"track", "barrier"}
VALID_ORDER_BYS = {"win_rate", "place_rate", "roi", "runners"}


@router.get("/trainer-win-rates")
async def get_trainer_win_rates(
    request: Request,
    track: str | None = None,
    surface: str | None = None,
    condition_category: str | None = None,
    distance_min: int | None = None,
    distance_max: int | None = None,
    race_class_group: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_runners: int = Query(default=5, ge=1),
    order_by: str = Query(default="win_rate"),
    group_by: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    return await _get_people_rates(
        request,
        role_column="re.trainer",
        role_label="trainer",
        track=track,
        surface=surface,
        condition_category=condition_category,
        distance_min=distance_min,
        distance_max=distance_max,
        race_class_group=race_class_group,
        date_from=date_from,
        date_to=date_to,
        min_runners=min_runners,
        order_by=order_by,
        group_by=group_by,
        limit=limit,
    )


@router.get("/jockey-win-rates")
async def get_jockey_win_rates(
    request: Request,
    track: str | None = None,
    surface: str | None = None,
    condition_category: str | None = None,
    distance_min: int | None = None,
    distance_max: int | None = None,
    race_class_group: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_runners: int = Query(default=5, ge=1),
    order_by: str = Query(default="win_rate"),
    group_by: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    return await _get_people_rates(
        request,
        role_column="re.jockey_or_driver",
        role_label="jockey",
        track=track,
        surface=surface,
        condition_category=condition_category,
        distance_min=distance_min,
        distance_max=distance_max,
        race_class_group=race_class_group,
        date_from=date_from,
        date_to=date_to,
        min_runners=min_runners,
        order_by=order_by,
        group_by=group_by,
        limit=limit,
    )


async def _get_people_rates(
    request: Request,
    *,
    role_column: str,
    role_label: str,
    track: str | None,
    surface: str | None,
    condition_category: str | None,
    distance_min: int | None,
    distance_max: int | None,
    race_class_group: str | None,
    date_from: str | None,
    date_to: str | None,
    min_runners: int,
    order_by: str,
    group_by: str | None,
    limit: int,
):
    validated_order = order_by if order_by in VALID_ORDER_BYS else "win_rate"
    validated_group = group_by if group_by in VALID_GROUP_BYS else None

    clauses = [
        f"{role_column} IS NOT NULL",
        "re.scratched = false",
        "re.final_position IS NOT NULL",
    ]
    params: list[Any] = []
    if track is not None:
        params.append(track)
        clauses.append(f"LOWER(m.track_name) = LOWER(${len(params)})")
    if surface is not None:
        params.append(surface)
        clauses.append(f"COALESCE(r.surface, m.surface) = ${len(params)}")
    if condition_category is not None:
        params.append(condition_category)
        clauses.append(f"LOWER(COALESCE(tc.condition_category, '')) = LOWER(${len(params)})")
    if distance_min is not None:
        params.append(distance_min)
        clauses.append(f"r.distance_m >= ${len(params)}")
    if distance_max is not None:
        params.append(distance_max)
        clauses.append(f"r.distance_m <= ${len(params)}")
    if race_class_group is not None:
        params.append(race_class_group)
        clauses.append(f"r.race_class_group = ${len(params)}")
    if date_from is not None:
        params.append(date_from)
        clauses.append(f"m.meeting_date >= ${len(params)}::date")
    if date_to is not None:
        params.append(date_to)
        clauses.append(f"m.meeting_date <= ${len(params)}::date")

    split_select = "NULL::text AS split_value"
    if validated_group == "track":
        split_select = "m.track_name AS split_value"
    elif validated_group == "barrier":
        split_select = "COALESCE(re.barrier_number::text, 'Unknown') AS split_value"

    rows = await fetch_all(
        request,
        f"""
        WITH latest_prices AS (
            SELECT DISTINCT ON (race_entry_id)
                race_entry_id,
                COALESCE(win_sp, win_price)::float AS closing_price
            FROM odds_snapshots
            WHERE COALESCE(win_sp, win_price) IS NOT NULL
            ORDER BY race_entry_id, captured_at DESC
        )
        SELECT
            {role_column} AS person,
            {split_select},
            re.final_position,
            lp.closing_price
        FROM race_entries re
        JOIN races r ON r.id = re.race_id
        JOIN meetings m ON m.id = r.meeting_id
        LEFT JOIN latest_prices lp ON lp.race_entry_id = re.id
        LEFT JOIN LATERAL (
            SELECT condition_category
            FROM track_condition_readings tcr
            WHERE tcr.race_id = r.id OR (tcr.race_id IS NULL AND tcr.meeting_id = m.id)
            ORDER BY CASE WHEN tcr.race_id = r.id THEN 0 ELSE 1 END, recorded_at DESC
            LIMIT 1
        ) tc ON TRUE
        WHERE {' AND '.join(clauses)}
        """,
        *params,
    )

    items = compute_person_metrics(rows, min_runners=min_runners, order_by=validated_order)[:limit]
    return {
        "role": role_label,
        "filters": {
            "track": track,
            "surface": surface,
            "condition_category": condition_category,
            "distance_min": distance_min,
            "distance_max": distance_max,
            "race_class_group": race_class_group,
            "date_from": date_from,
            "date_to": date_to,
            "min_runners": min_runners,
            "group_by": validated_group,
            "order_by": validated_order,
        },
        "items": items,
    }
